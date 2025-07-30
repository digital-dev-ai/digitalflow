from collections import defaultdict
from dateutil import parser
from datetime import datetime
import json
import os
from pathlib import Path
import re
from airflow.models import Variable
from typing import Any
import uuid
import numpy as np
from utils.db import dococr_query_util
from utils.com import json_util
import re


RESULT_FOLDER = Variable.get("RESULT_FOLDER", default_var="/opt/airflow/data/result")
TEMP_FOLDER = Variable.get("TEMP_FOLDER", default_var="/opt/airflow/data/temp")
STEP_INFO_DEFAULT = {
    "name":"match block default",
    "type":"match_block_step_list",
    "step_list":[
        {"name":"save","param":{"save_key":"tmp_save"}}
    ]
}

def export_ocr_output(doc_info:dict, step_info:dict=None, result_map:dict=None) -> Any:
    """
    이미지 결과 저장 함수
    :param data: 이미지(Any) 데이터
    :param step_info: 전처리 단계 정보 (기본값은 STEP_INFO_DEFAULT)
    :param result_map: 결과를 저장할 맵 (기본값은 빈 딕셔너리)
    :return: 전처리된 이미지 또는 결과
    """
    if step_info is None:
        step_info = STEP_INFO_DEFAULT
    if result_map is None:
        result_map = {}
    step_list = step_info.get("step_list", STEP_INFO_DEFAULT["step_list"])
    return export_ocr_output_step_list(doc_info=doc_info, step_list=step_list, result_map=result_map)

def export_ocr_output_step_list(doc_info:dict, step_list:dict=None, result_map:dict=None) -> Any:
    """
    이미지 결과 저장 함수
    :param data: 이미지(Any)와 파일정보(dict)가 담긴 목록
    :param step_list: 전처리 단계 정보 (기본값은 STEP_INFO_DEFAULT["step_list"])
    :param result_map: 결과를 저장할 맵 (기본값은 빈 딕셔너리)
    :return: 전처리된 이미지 또는 결과
    """
    if step_list is None:
        step_list = STEP_INFO_DEFAULT["step_list"]
    if result_map is None:
        result_map = {}
    process_id = f"_cln_{str(uuid.uuid4())}"
    result_map["process_id"] = process_id
    result_map["folder_path"] = result_map.get("folder_path",f"{TEMP_FOLDER}/{process_id}")
    result_map["cache"] = {}
    result_map["save_path"] = {}
    
    for stepinfo in step_list:
        print("step :",stepinfo["name"])
        if stepinfo["name"] not in function_map:
            print(f"경고: '{stepinfo['name']}' 함수가 정의되지 않아 다음 단계를 진행합니다.")
            continue  # 정의되지 않은 함수는 건너뜀
        function_info = function_map[stepinfo["name"]]
        function_info["function"](doc_info,**stepinfo["param"],result_map=result_map)

    return result_map

def insert_ocr_result(
    doc_info: dict,
    result_map: dict = None,
    **kwargs
) -> tuple[Any,dict]:
    doc_class_id = (doc_info["doc_class_id"],)
    structed_doc = doc_info["structed_doc"]
    dococr_query_util.insert_structed_ocr_result(doc_class_id,structed_doc)

def _save(file_path:str,save_key:str="tmp",result_map:dict=None):
    if not result_map:
        result_map = {}
    result_map["save_path"][save_key]=file_path 

    
function_map = {
    "insert_ocr_result": {"function": insert_ocr_result, "param": "ocr_type,keep_chars"},
}