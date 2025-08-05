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
from utils.ai import lilt_classify_by_subject_line_util
from utils.ai import ml_classify_by_subject_line_util
from utils.ocr import separate_area_util
from utils.db import dococr_query_util
from utils.com import file_util, json_util
from utils.img import type_convert_util
from airflow.models import Variable,XCom
from datetime import datetime
import pytesseract

RESULT_FOLDER = Variable.get("RESULT_FOLDER", default_var="/opt/airflow/data/result")
TEMP_FOLDER = Variable.get("TEMP_FOLDER", default_var="/opt/airflow/data/temp")

@task
def img_classify_task(ai_info: dict, file_info: dict, target_key: str, **context) -> dict:
    """ai_info로 LiLT 모델로 이미지 분류 결과를 file_info에 저장하여 반환"""
    processor_name = ai_info["processor_name"]
    if processor_name == "ML":
        classify_result = ml_classify_by_subject_line_util.classify(ai_info, file_info, target_key)
    if processor_name == "SCUT-DLVCLab/lilt-roberta-en-base":
        classify_result = lilt_classify_by_subject_line_util.classify(ai_info, file_info, target_key)
    
    class_key = ai_info["class_key"]
    classify_map = file_info.get("classify",{})
    classify_map[class_key] = classify_result
    file_info["classify"] = classify_map
    
    
    # 결과 폴더에 파일 복사
    run_id = context['dag_run'].run_id
    target_id = file_info.get("layout_id",file_info["file_id"])
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
        target_id = file_info.get("layout_id",file_info["file_id"])
        temp_folder = Path(TEMP_FOLDER)/run_id
        file_util.file_copy(file_info["file_path"]["_origin"],temp_folder/Path(file_info["file_path"]["_origin"]).name)
        dococr_query_util.update_map("updateTargetContent",(json.dumps(file_info),run_id,target_id))

    return file_infos