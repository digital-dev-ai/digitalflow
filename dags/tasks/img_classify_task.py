import os
from airflow.decorators import task
from collections import Counter
from pathlib import Path
from PIL import Image
import cv2
import numpy as np
import json
from typing import Any,List
import uuid
from utils.ocr import separate_area_util
from utils.db import dococr_query_util
from utils.com import file_util, json_util
from utils.img import type_convert_util
from airflow.models import Variable,XCom
from datetime import datetime
import pytesseract
from transformers import AutoProcessor, AutoModelForSequenceClassification
import torch
import torch.nn.functional as F

RESULT_FOLDER = Variable.get("RESULT_FOLDER", default_var="/opt/airflow/data/result")
TEMP_FOLDER = Variable.get("TEMP_FOLDER", default_var="/opt/airflow/data/temp")

@task
def img_classify_task(ai_info: dict, file_info: dict, target_key: str, **context) -> dict:
    """LiLT 모델로 이미지 분류 결과를 file_info에 저장하여 반환"""
    ai_dir = ai_info["ai_dir"]
    save_input = ai_info["save_input"]
    class_key = ai_info["class_key"]
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

    # 실행
    if target_key not in file_info["file_path"]:
        image_path = file_info["file_path"]["_origin"]
    image_path = file_info["file_path"][target_key]
    pred, confidence, input_kwargs = predict(image_path, model, processor, device)
    if save_input:
        classify_result = {"pred": pred, "confidence": confidence, "input_kwargs":input_kwargs}
    else :
        classify_result = {"pred": pred, "confidence": confidence}

    
    classify_map = file_info.get("classify",{})
    classify_map[class_key] = classify_result
    file_info["classify"] = classify_map

    # 결과 폴더에 파일 복사
    run_id = context['dag_run'].run_id
    target_id = file_info["file_id"]
    dococr_query_util.update_map("updateTargetContent",(json.dumps(file_info),run_id,target_id))
    file_info["status"] = "success"
    return file_info
    

@task
def aggregate_classify_results_task(file_infos:List,class_keys,**context):
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
            classify_result = file_info.get("classify", {})
            print(classify_result)
            class_result = classify_result.get(class_key, {})
            pred = class_result.get("pred", 0)
            conf = class_result.get("confidence", 0)
            print(class_key, " - ", pred, " ", conf)
            if pred == 1:
                if conf > max_conf:
                    max_conf = conf
                    best_class = class_key # layout_class_id
                    print("max_conf:", max_conf, "best_class:", best_class, "pred", pred)
        # 신뢰도가 0.8을 초과하면 최종 클래스로 설정, 아니면 "None"으로 처리
        if max_conf>0.9:
            file_info["layout_class_id"] = best_class
            file_info["confidence"] = max_conf
        else:
            file_info["layout_class_id"] = "None"
            file_info["confidence"] = max_conf

        # 결과 폴더에 파일 복사
        run_id = context['dag_run'].run_id
        target_id = file_info["file_id"]
        temp_folder = Path(TEMP_FOLDER)/run_id
        file_util.file_copy(file_info["file_path"]["_origin"],temp_folder/Path(file_info["file_path"]["_origin"]).name)
        dococr_query_util.update_map("updateTargetContent",(json.dumps(file_info),run_id,target_id))

    return file_infos

def predict(image_path, model, processor, device):
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
        print("pixel_values is in model_input_names")
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
    return pred, confidence, input_kwargs

def preprocess_image(image_path):
    """이미지 로드, OCR, 바운딩 박스 정규화"""
    image = Image.open(image_path).convert("RGB")
    image_width, image_height = image.size

    process_id = f"_ic_{str(uuid.uuid4())}"
    # 1. 상단 헤더 영역만 분리하여 OCR 수행
    header_img, _ = separate_area_util.separate_area_step_list(
        image, data_type="pil", output_type="pil",
        step_list=[
            {"name":"save","param":{"save_key":"_origin","tmp_save":True}},
            {"name" : "separate_areas_set1", "param": {"area_name":"doc_subject","area_type":"top_center","area_ratio":[-0.083,0.068,0.188,0.068],"iter_save":False}},
            {"name":"save","param":{"save_key":"_cutted","tmp_save":True}}
        ],
        result_map={"folder_path":process_id}
    )
    header_width, header_height = header_img.size
    
    try:
        print("3-2. OCR 수행 시작")
        data = pytesseract.image_to_data(
            header_img, output_type=pytesseract.Output.DICT, lang='kor+eng', config='--psm 6 --oem 3')
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
            norm_bbox = normalize_bbox(bbox, header_width, header_height)
            boxes.append(norm_bbox)
    
    # 2. 표(원본) 영역에서 수평/수직선만 검출 (OCR X)
    cv_image = np.array(image)
    if len(cv_image.shape) == 3:
        cv_image = cv2.cvtColor(cv_image, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(cv_image, 180, 255, cv2.THRESH_BINARY_INV)
    # binary = cv2.MORPH_DILATE 작성중.

    # 수평선 검출 (비율 기반 커널)
    dilate_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
    detect_horizontal = cv2.morphologyEx(binary, cv2.MORPH_DILATE, dilate_kernel, iterations=1)
    horizontal_kernel_ratio = 0.8
    vertical_kernel_ratio = 0.038
    
    horizontal_kernel_size = max(1, int(image_width * horizontal_kernel_ratio))
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (horizontal_kernel_size, 1))
    detect_horizontal = cv2.morphologyEx(detect_horizontal, cv2.MORPH_OPEN, horizontal_kernel, iterations=1)
    detect_horizontal = cv2.morphologyEx(detect_horizontal, cv2.MORPH_CLOSE, horizontal_kernel, iterations=2)
    contours_h, _ = cv2.findContours(detect_horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours_h:
        x, y, w, h = cv2.boundingRect(cnt)
        bbox = (x, y, x + w, y + h)
        norm_bbox = normalize_bbox(bbox, image_width, image_height)
        words.append('─')
        boxes.append(norm_bbox)
    separate_area_util.separate_area_step_list(detect_horizontal, data_type='np_bgr', output_type='np_bgr',
        step_list=[{"name":"save","param":{"save_key":"_h_contour","tmp_save":True}}], result_map={"folder_path":process_id})

    # 수직선 검출 (비율 기반 커널)
    vertical_kernel_size = max(1, int(image_height * vertical_kernel_ratio))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, vertical_kernel_size))
    detect_vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel, iterations=2)
    contours_v, _ = cv2.findContours(detect_vertical, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours_v:
        x, y, w, h = cv2.boundingRect(cnt)
        bbox = (x, y, x + w, y + h)
        norm_bbox = normalize_bbox(bbox, image_width, image_height)
        words.append('│')
        boxes.append(norm_bbox)
    separate_area_util.separate_area_step_list(detect_vertical, data_type='np_bgr', output_type='np_bgr',
        step_list=[{"name":"save","param":{"save_key":"_v_contour","tmp_save":True}}], result_map={"folder_path":process_id})
    # data에 words, boxes만 저장
    data['words'] = words
    data['boxes'] = boxes
    # data = {'words': words, 'boxes': boxes}
    ocr_save_dir = "/opt/airflow/data/class/a_class/classify/ocr"
    os.makedirs(ocr_save_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    ocr_save_path = os.path.join(ocr_save_dir, f"{base_name}_ocr.json")
    json_util.save(ocr_save_path, data)


    if len(words) != len(boxes):
        min_len = min(len(words), len(boxes))
        words = words[:min_len]
        boxes = boxes[:min_len]
    if not words:
        words = ["[UNK]"]
        boxes = [[0, 0, 100, 100]]
    print(f"3-4. 전처리 완료 (단어 수: {len(words)}, 박스 수: {len(boxes)})")
    return image, words, boxes



def normalize_bbox(bbox, image_width, image_height, image1000=True):
    """바운딩 박스 정규화 (이미지 크기 기준 → 1000 기준)"""
    x1, y1, x2, y2 = bbox
    if image1000:
        x1 = int(1000 * (x1 / image_width))
        y1 = int(1000 * (y1 / image_height))
        x2 = int(1000 * (x2 / image_width))
        y2 = int(1000 * (y2 / image_height))
    return [x1, y1, x2, y2]

