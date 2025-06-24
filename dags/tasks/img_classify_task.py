from airflow.decorators import task
from collections import Counter
from pathlib import Path
from PIL import Image
import numpy as np
import cv2, os
from typing import Any,List
import uuid
from utils.db.maria_util import insert_map
from utils import file_util, json_util
from utils import type_convert_util
from airflow.models import Variable,XCom
from datetime import datetime
import pytesseract
from scipy.ndimage import interpolation as inter
from transformers import AutoModelForSequenceClassification, AutoProcessor
import torch
import torch.nn.functional as F  # 상단에 추가

RESULT_FOLDER = Variable.get("RESULT_FOLDER", default_var="/opt/airflow/data/result")
TEMP_FOLDER = Variable.get("TEMP_FOLDER", default_var="/opt/airflow/data/temp")
@task
def img_classify_task(ai_info:dict,file_info:dict,result_key:str="result",class_key:str="class")->dict:
    ai_dir = ai_info["ai_dir"]
    model_name = ai_info["model_name"]
    processor = AutoProcessor.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(ai_dir)
    model.eval()
    device = torch.device("cpu")  # 혹은 "cuda"
    model.to(device)

    def preprocess_image(image_path):
        image = Image.open(image_path).convert("RGB")
        image = image.resize((224, 224))
        #text = pytesseract.image_to_string(image, lang='kor+eng', config='--psm 4 --oem 3')
        #words = text.split()[:50] or ["[UNK]"]
        #boxes = [[0,0,100,100]] * len(words)
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        words = data['text'][:50] if data['text'] else ["[UNK]"]
        boxes = [(x, y, x+w, y+h) for x,y,w,h in zip(data['left'], data['top'], data['width'], data['height'])]
        boxes = boxes[:len(words)]
        if not boxes:
            boxes = [[0,0,100,100]]
        return image, words, boxes

    def predict(image_path, model, processor):
        image, words, boxes = preprocess_image(image_path)
        encoding = processor(
            images=image,
            text=words, boxes=boxes,
            return_tensors="pt", truncation=True, padding="max_length", max_length=128
        )
        with torch.no_grad():
            outputs = model(**{k: v.to(device) for k, v in encoding.items()})
            logits = outputs.logits
            probs = F.softmax(logits, dim=1)
            pred = torch.argmax(probs, dim=1).item()
            confidence = probs[0, pred].item()
        print("Input keys to processor:", encoding.keys()) 
        return pred, confidence
    

    image_path = file_info[result_key]["result_file_map"]["_result"]
    pred, confidence = predict(image_path, model, processor)
    file_info["classify"]={}
    file_info["classify"][class_key] = {"pred":pred, "confidence":confidence}
    return file_info

@task
def aggregate_classify_results_task(file_infos,class_keys,**context):
    for file_info in file_infos:
        max_conf = -1
        best_class = None
        for class_key in class_keys:
            class_result = file_info.get(class_key, {})
            conf = class_result.get("confidence", 0)
            if conf > max_conf:
                max_conf = conf
                best_class = class_key
        if max_conf>0.8:
            file_info["class"] = best_class
            file_info["confidence"] = max_conf
        else:
            file_info["class"] = "None"
            file_info["confidence"] = max_conf
        run_id = context['dag_run'].run_id
        target_id = file_info["file_id"]
        result_folder = Path(RESULT_FOLDER)/run_id
        file_util.file_copy(file_info["file_path"],result_folder/Path(file_info["file_path"]).name)
        insert_map("insertClassifyResult",(run_id,target_id,file_info))
    return file_infos
