from collections import Counter, deque
from pathlib import Path
from airflow.models import Variable, XCom
from typing import Any, List, Dict, Tuple
import uuid
import cv2
import numpy as np
import pytesseract
from scipy.ndimage import interpolation as inter
from utils.dev import draw_block_box_util
from utils.com import json_util, file_util
from utils.img import type_convert_util
from typing import Tuple, List
import numpy as np
import cv2
from pathlib import Path

RESULT_FOLDER = Variable.get("RESULT_FOLDER", default_var="/opt/airflow/data/result")
TEMP_FOLDER = Variable.get("TEMP_FOLDER", default_var="/opt/airflow/data/temp")
STEP_INFO_DEFAULT = {
    "name":"separate block default",
    "type":"separate_block_step_list",
    "step_list":[
        {"name":"save","param":{"save_key":"tmp_save"}}
    ]
}

def ocr(block_data:Tuple[Any,Dict], input_img_type:str="np_bgr", step_info:Dict=None, result_map:dict=None) -> Dict:
    """
    이미지 전처리 함수
    :param data: 이미지 파일 경로 또는 numpy 배열
    :param data_type: 입력 데이터의 타입 ("file_path", "np_bgr", "np_gray" 등)
    :param step_info: 전처리 단계 정보 (기본값은 STEP_INFO_DEFAULT)
    :param result_map: 결과를 저장할 맵 (기본값은 빈 딕셔너리)
    :return: 전처리된 이미지 또는 결과
    """
    if step_info is None:
        step_info = STEP_INFO_DEFAULT
    if result_map is None:
        result_map = {}
    step_list = step_info.get("step_list", STEP_INFO_DEFAULT["step_list"])
    return ocr_step_list(block_data=block_data, input_img_type=input_img_type, step_list=step_list, result_map=result_map)

def ocr_step_list(block_data:Tuple[Any,Dict], input_img_type:str="np_bgr", step_list:List[Dict]=None, result_map:dict=None) -> Dict:
    """
    이미지 전처리 함수
    :param data: 이미지 파일 경로 또는 numpy 배열
    :param data_type: 입력 데이터의 타입 ("file_path", "np_bgr", "np_gray" 등)
    :param step_list: 전처리 단계 정보 (기본값은 STEP_INFO_DEFAULT["step_list"])
    :param result_map: 결과를 저장할 맵 (기본값은 빈 딕셔너리)
    :return: 전처리된 이미지 또는 결과
    """
    if step_list is None:
        step_list = STEP_INFO_DEFAULT["step_list"]
    if result_map is None:
        result_map = {}
    process_id = str(uuid.uuid4())
    result_map["process_id"] = f"_spb{process_id}"
    result_map["folder_path"] = result_map.get("folder_path",process_id)
    result_map["cache"] = {}
    result_map["save_path"] = {}
    
    output = block_data
    before_output_type = input_img_type

    for idx, stepinfo in enumerate(step_list):
        print("step :",stepinfo["name"])
        if stepinfo["name"] not in function_map:
            print(f"경고: '{stepinfo['name']}' 함수가 정의되지 않아 다음 단계를 진행합니다.")
            continue  # 정의되지 않은 함수는 건너뜀
        function_info = function_map[stepinfo["name"]]
        convert_param = stepinfo.get("convert_param", {})
        input = (type_convert_util.convert_type(output[0],before_output_type,function_info["input_type"],params=convert_param), output[1])
        output = function_info["function"](input,**stepinfo["param"],result_map=result_map)
        before_output_type = function_info["output_type"]
    
    return output[1]

def cache(block_data:Tuple[Any,Dict],cache_key:str,result_map:dict)->Tuple[Any,Dict]:
    result_map["cache"][f"filepath_{cache_key}"] = block_data
    return block_data

def load(_,cache_key:str,result_map:dict)->Tuple[Any,Dict]:
    return result_map["cache"][f"filepath_{cache_key}"]

    if tmp_save:
        if result_map.get("folder_path", "abcd").startswith(TEMP_FOLDER) or result_map.get("folder_path", "abcd").startswith(RESULT_FOLDER) :
            save_path = result_map.get("folder_path","temp") / f"{save_key}.png"
        else : 
            save_path = Path(TEMP_FOLDER) / result_map.get("folder_path","temp") / f"{save_key}.png"
        save_path = file_util.file_copy(file_path,save_path)
    else:
        save_path = file_path
    result_map["save_path"][save_key]=save_path
    return file_path


def save(block_data:Tuple[Any,Dict],save_key:str,result_map:dict,tmp_save:bool=False)->Tuple[Any,Dict]:
    print("save called with save_key:", save_key)
    if not save_key:
        save_key = "tmp"
    if tmp_save:
        if result_map.get("folder_path", "temp").startswith(TEMP_FOLDER) or result_map.get("folder_path", "temp").startswith(RESULT_FOLDER) :
            save_path = result_map.get("folder_path","temp") / f"{save_key}.png"
        else : 
            save_path = Path(TEMP_FOLDER) / result_map.get("folder_path","temp") / f"{save_key}.png"

        img_save_path = Path(TEMP_FOLDER) / result_map.get("folder_path",result_map.get("process_id","temp")) / f"{save_key}.png"
        img_save_path = file_util.file_copy(block_data[0],img_save_path) # 복사 후 실제 경로 전달(중복 방지로 인한 파일명 변경 등 반영)
        json_save_path = Path(TEMP_FOLDER) / result_map.get("folder_path",result_map.get("process_id","temp")) / f"{save_key}.json"
        json_util.save(str(json_save_path),block_data[1])
    else:
        img_save_path = block_data[0]
    result = (img_save_path, block_data[1])
    result_map["save_path"][save_key]=result
    return result

def tesseract(block_data:Tuple[Any,Dict], lang:str="kor+eng", config:str="--oem 3 --psm 3", iter_save:bool=False, result_map:dict=None) -> List[Tuple[Any, Dict]]:
    img_np_bgr, block_map = block_data
    
    # 
    gray = cv2.cvtColor(img_np_bgr, cv2.COLOR_BGR2GRAY)
    
    # 스케일 -> 이진화
    # # 확대
    # x_scale = 2.0
    # y_scale = 2.0
    # scaled = cv2.resize(gray, None, fx=x_scale, fy=y_scale, interpolation=cv2.INTER_LINEAR)

    # #강화된 이진화
    # thresh = cv2.adaptiveThreshold(
    #     scaled, 255,
    #     cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
    #     cv2.THRESH_BINARY, 11, 2
    # )

    # 이진화 -> 스케일
    #강화된 이진화
    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )

    # 확대
    x_scale = 2.0
    y_scale = 2.0
    scaled = cv2.resize(thresh, None, fx=x_scale, fy=y_scale, interpolation=cv2.INTER_LINEAR)

    # 🔧 morphology로 결손 복원
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    thresh = cv2.morphologyEx(scaled, cv2.MORPH_OPEN, kernel, iterations=1)
    # thresh = cv2.morphologyEx(scaled, cv2.MORPH_CLOSE, kernel, iterations=1)
    
    data = pytesseract.image_to_data(
        thresh, lang=lang, config=config, output_type=pytesseract.Output.DICT
    )
    
    # draw_block_list = []
    # for i in range(len(data['level'])):
    #     block_id = data['text'][i]
    #     block_box = [data['left'][i], data['top'][i], data['width'][i], data['height'][i]]
    #     draw_block_list.append({'block_id': block_id, 'block_box': block_box})
    #draw_block_box_util.draw_block_box_step_list((thresh, draw_block_list), input_img_type="np_gray", step_list=[{"name": "draw_block_box_xywh", "param": {"box_color": 1, "iter_save": True}}],result_map={"folder_path":result_map["process_id"]})
    converted = data.copy()
    for key in ['left', 'width']:
        converted[key] = [value / x_scale for value in data[key]]
    for key in ['top', 'height']:
        converted[key] = [value / y_scale for value in data[key]]
    
    # converted_draw_block_list = []
    # for i in range(len(converted['level'])):
    #     block_id = converted['text'][i]
    #     block_box = [converted['left'][i], converted['top'][i], converted['width'][i], converted['height'][i]]
    #     converted_draw_block_list.append({'block_id': block_id, 'block_box': block_box})
    #draw_block_box_util.draw_block_box_step_list((img_np_bgr, converted_draw_block_list), input_img_type="np_bgr", step_list=[{"name": "draw_block_box_xywh", "param": {"box_color": 1, "iter_save": True}}],result_map={"folder_path":result_map["process_id"]})
    combined_text = ' '.join([word for word in data['text'] if word.strip() != ''])
    block_map['ocr'] = {"summary":combined_text,"tesseract":converted}
    if iter_save:
        save((type_convert_util.convert_type(thresh, "np_gray", "file_path"), block_map), result_map=result_map, save_key=block_map["block_id"], tmp_save=True)
   
    return (img_np_bgr,block_map)
function_map = {
    #common
    "cache": {"function": cache, "input_type": "file_path", "output_type": "file_path","param":"cache_key"},
    "load": {"function": load, "input_type": "any", "output_type": "file_path","param":"cache_key"},
    "save": {"function": save, "input_type": "file_path", "output_type": "file_path","param":"save_key"},
    #ocr
    "tesseract": {"function": tesseract, "input_type": "np_bgr", "output_type": "np_bgr", "param": "lang,config,iter_save"},
    
}