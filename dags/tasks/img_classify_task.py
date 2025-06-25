from airflow.decorators import task
from collections import Counter
from pathlib import Path
from PIL import Image
import numpy as np
import json
from typing import Any,List
import uuid
from utils.db.maria_util import insert_map
from utils import file_util, json_util
from utils import type_convert_util
from airflow.models import Variable,XCom
from datetime import datetime
import pytesseract
from transformers import AutoProcessor, AutoModelForSequenceClassification
import torch
import torch.nn.functional as F

RESULT_FOLDER = Variable.get("RESULT_FOLDER", default_var="/opt/airflow/data/result")
TEMP_FOLDER = Variable.get("TEMP_FOLDER", default_var="/opt/airflow/data/temp")

@task
def img_classify_task(ai_info: dict, file_info: dict, result_key: str = "result", class_key: str = "class") -> dict:
    """LiLT 모델로 이미지 분류 결과를 file_info에 저장하여 반환"""
    ai_dir = ai_info["ai_dir"]
    processor_name = ai_info["processor_name"]
    device = torch.device("cpu")  # 또는 "cuda"
    torch.set_default_dtype(torch.float32)

    # 프로세서와 모델 로드
    processor = AutoProcessor.from_pretrained(processor_name, use_fast=True)
    a = processor.model_input_names
    model = AutoModelForSequenceClassification.from_pretrained(ai_dir)
    
    model.to(device)
    model.eval()
    print("1. 모델 및 프로세서 로드 완료")

    def normalize_bbox(bbox, image_width, image1000=True):
        """바운딩 박스 정규화 (이미지 크기 기준 → 1000 기준)"""
        x1, y1, x2, y2 = bbox
        if image1000:
            x1 = int(1000 * (x1 / image_width))
            x2 = int(1000 * (x2 / image_width))
            y1 = int(1000 * (y1 / image_width))  # 이미지 resize 없을 경우 image_height 사용 권장
            y2 = int(1000 * (y2 / image_width))  # (단, 이미지 정방형 가정 시 image_width로 통일 가능)
        return [x1, y1, x2, y2]

    def preprocess_image(image_path):
        """이미지 로드, OCR, 바운딩 박스 정규화"""
        image = Image.open(image_path).convert("RGB")
        image_width, image_height = image.size

        try:
            print("3-2. OCR 수행 시작")
            data = pytesseract.image_to_data(
                image, output_type=pytesseract.Output.DICT, lang='kor+eng', config='--psm 4 --oem 3'
            )
            print("3-3. OCR 수행 완료")
        except Exception as e:
            print(f"OCR error: {e}")
            data = {"text": [], "left": [], "top": [], "width": [], "height": []}

        words = []
        boxes = []
        for word, x, y, w, h in zip(data['text'], data['left'], data['top'], data['width'], data['height']):
            if word.strip():
                words.append(word.strip())
                bbox = (x, y, x + w, y + h)
                norm_bbox = normalize_bbox(bbox, image_width)
                boxes.append(norm_bbox)

        if len(words) != len(boxes):
            min_len = min(len(words), len(boxes))
            words = words[:min_len]
            boxes = boxes[:min_len]
        if not words:
            words = ["[UNK]"]
            boxes = [[0, 0, 100, 100]]
        print(f"3-4. 전처리 완료 (단어 수: {len(words)}, 박스 수: {len(boxes)})")
        return image, words, boxes

    def predict(image_path, model, processor):
        """예측 수행"""
        image, words, boxes = preprocess_image(image_path)
        print("4-1. 모델 입력 생성 시작")
        input_kwargs = {
            "text": words,
            "boxes": boxes,
            "return_tensors": "pt",
            "truncation": True,
            "padding": "max_length",
            "max_length": 128
        }
        if "pixel_values" in processor.model_input_names:
            input_kwargs["images"] = image  # 이미지가 필요하면 추가
        
        encoding = processor(**input_kwargs)
        
        print("4-2. 모델 입력 생성 완료")
        with torch.no_grad():
            print("4-3. 모델 예측 중...")
            inputs = {k: v.to(device) for k, v in encoding.items()}
            outputs = model(**inputs)
            logits = outputs.logits
            probs = F.softmax(logits, dim=1)
            pred = torch.argmax(probs, dim=1).item()
            confidence = probs[0, pred].item()
        return pred, confidence

    # 실행
    if result_key not in file_info:
        image_path = file_info.file_path
    image_path = file_info[result_key]["result_file_map"]["_result"]
    pred, confidence = predict(image_path, model, processor)
    file_info["classify"] = {}
    file_info["classify"][class_key] = {"pred": pred, "confidence": confidence}
    return file_info

@task
def aggregate_classify_results_task(file_infos,class_keys,**context):
    """
    파일 정보 리스트에서 각 파일별로 분류 결과를 종합하고, 가장 신뢰도가 높은 클래스로 최종 분류 결과를 저장하는 함수.
    결과는 파일 정보에 추가되고, 분류 결과 및 파일 복사, DB 저장 등의 후처리를 수행한다.

    Args:
        file_infos (list): 각 파일의 정보(분류 결과 포함)가 담긴 딕셔너리 리스트
        class_keys (list): 분류 기준이 되는 클래스 키 리스트
        context (dict): Airflow 등에서 전달되는 context 정보(예: dag_run 등)
    Returns:
        list: 최종 분류 결과가 추가된 파일 정보 리스트
    """
    for file_info in file_infos:
        # 각 파일별로 최대 신뢰도와 해당 클래스를 찾기 위한 초기화
        max_conf = -1
        best_class = None
        # 각 클래스별로 신뢰도 비교
        for class_key in class_keys:
            print(class_key,"시작") 
            print("1file_info",file_info)
            classify_result = file_info.get("classify", {})
            print("2classify_result",classify_result)
            class_result = classify_result.get(class_key, {})
            print("3class_result",class_result)
            pred = class_result.get("pred", 0)
            conf = class_result.get("confidence", 0)
            print(class_key, " - ", pred, " ", conf)
            if pred == 1:
                if conf > max_conf:
                    max_conf = conf
                    best_class = class_key
                    print("max_conf:", max_conf, "best_class:", best_class, "pred", pred)
        # 신뢰도가 0.8을 초과하면 최종 클래스로 설정, 아니면 "None"으로 처리
        if max_conf>0.9:
            file_info["class"] = best_class
            file_info["confidence"] = max_conf
        else:
            file_info["class"] = "None"
            file_info["confidence"] = max_conf

        # 결과 폴더에 파일 복사
        run_id = context['dag_run'].run_id
        target_id = file_info["file_id"]
        result_folder = Path(RESULT_FOLDER)/run_id
        file_util.file_copy(file_info["file_path"],result_folder/Path(file_info["file_path"]).name)
        insert_map("insertClassifyResult",(run_id,target_id,json.dumps([file_info])))

    return file_infos
