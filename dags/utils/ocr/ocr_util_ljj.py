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

def save(block_data:Tuple[Any,Dict],save_key:str,result_map:dict,tmp_save:bool=False)->Tuple[Any,Dict]:
    print("save called with save_key:", save_key)
    if not save_key:
        save_key = "tmp"
    if tmp_save:
        img_save_path = Path(TEMP_FOLDER) / result_map.get("folder_path",result_map.get("process_id","temp")) / f"{save_key}.png"
        img_save_path = file_util.file_copy(block_data[0],img_save_path) # 복사 후 실제 경로 전달(중복 방지로 인한 파일명 변경 등 반영)
        json_save_path = Path(TEMP_FOLDER) / result_map.get("folder_path",result_map.get("process_id","temp")) / f"{save_key}.json"
        json_util.save(str(json_save_path),block_data[1])
    else:
        img_save_path = block_data[0]
    result = (img_save_path, block_data[1])
    result_map["save_path"][save_key]=result
    return result

def tesseract(block_data:Tuple[Any,Dict], lang:str="kor", config:str="--oem 3 --psm 3", iter_save:bool=False, result_map:dict=None) -> List[Tuple[Any, Dict]]:
    img_np_bgr, block_map = block_data
    # psm 명시 필요.
    
    gray = cv2.cvtColor(img_np_bgr, cv2.COLOR_BGR2GRAY)
    
    # 스케일 -> 이진화
    # # 확대
    x_scale = 2.0
    y_scale = 2.0
    scaled = cv2.resize(gray, None, fx=x_scale, fy=y_scale, interpolation=cv2.INTER_LINEAR)

    #강화된 이진화
    # thresh = cv2.adaptiveThreshold(
    #     scaled, 255,
    #     cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
    #     cv2.THRESH_BINARY, 11, 2
    # )

    _, thresh = cv2.threshold(scaled, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # # 이진화 -> 스케일
    # #강화된 이진화
    # thresh = cv2.adaptiveThreshold(
    #     gray, 255,
    #     cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
    #     cv2.THRESH_BINARY, 11, 2
    # )

    # # 확대
    # x_scale = 2.0
    # y_scale = 2.0
    # scaled = cv2.resize(thresh, None, fx=x_scale, fy=y_scale, interpolation=cv2.INTER_LINEAR)



    # 🔧 morphology로 결손 복원
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5,3))
    # thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=1)
    
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

    # 단어 리스트 추출 및 띄어쓰기 보정 텍스트 생성
    word_details = _extract_word_details_from_tesseract_data(converted)
    full_text = _intelligently_join_words(word_details)
    converted['full_text'] = full_text
    block_map['ocr'] = {"tesseract":converted}

    # # 단어 리스트 추출 및 띄어쓰기 보정 텍스트 생성
    # word_details = _extract_word_details_from_tesseract_data(converted)
    # full_text = _intelligently_join_words(word_details)
    # block_map['ocr'][-1]['full_text'] = full_text  # block_map에 저장 (또는 result_map에 저장해도 됨)


    if iter_save:
        save((type_convert_util.convert_type(thresh, "np_gray", "file_path"), block_map), result_map=result_map, save_key=block_map["block_id"], tmp_save=True)
   
    return (img_np_bgr,block_map)

def _extract_word_details_from_tesseract_data(data: dict) -> list:
    """
    pytesseract image_to_data 결과(dict)에서 단어 리스트 추출
    """
    word_details = []
    num_items = len(data['level'])
    for i in range(num_items):
        if int(data['conf'][i]) > -1 and data['text'][i].strip():
            word_details.append({
                'level': data['level'][i],
                'page_num': data['page_num'][i],
                'block_num': data['block_num'][i],
                'par_num': data['par_num'][i],
                'line_num': data['line_num'][i],
                'word_num': data['word_num'][i],
                'left': data['left'][i],
                'top': data['top'][i],
                'width': data['width'][i],
                'height': data['height'][i],
                'conf': data['conf'][i],
                'text': data['text'][i],
            })
    return word_details

def _intelligently_join_words(word_details: list[dict], space_threshold_ratio: float = 0.55) -> str:
    """
    OCR로 인식된 단어들을 간격에 따라 지능적으로 연결
    - 단어 간 간격이 임계값(space_threshold_ratio)보다 작으면 붙여쓰고, 크면 띄어씀
    - 같은 줄에 있는 단어들끼리만 비교함

    Args:
        word_details (list[dict]): Tesseract의 image_to_data에서 나온 상세 단어 정보 리스트.
        space_threshold_ratio (float): 문자 평균 높이 대비 띄어쓰기 간격 임계값 비율.

    Returns:
        str: 띄어쓰기가 보정된 전체 텍스트.
    """
    if not word_details:
        return ""

    # 단어들을 block_num, par_num, line_num 기준으로 그룹화
    lines = {}
    for word in word_details:
        # 유효한 단어만 처리 (텍스트가 있고, 신뢰도가 0 이상)
        if word['text'].strip() and int(word['conf']) >= 0:
            line_key = (word['block_num'], word['par_num'], word['line_num'])
            if line_key not in lines:
                lines[line_key] = []
            lines[line_key].append(word)

    full_text_parts = []
    # 정렬된 라인 키를 순회
    for line_key in sorted(lines.keys()):
        words_in_line = sorted(lines[line_key], key=lambda w: w['left'])
        if not words_in_line:
            continue

        # 라인별 평균 문자 높이를 기준으로 띄어쓰기 임계값 설정
        avg_height = np.mean([w['height'] for w in words_in_line if w['height'] > 0])
        space_threshold = avg_height * space_threshold_ratio

        line_text = words_in_line[0]['text']
        for i in range(len(words_in_line) - 1):
            gap = words_in_line[i+1]['left'] - (words_in_line[i]['left'] + words_in_line[i]['width'])
            line_text += '' if gap < space_threshold else ' '
            line_text += words_in_line[i+1]['text']
        full_text_parts.append(line_text)

    return '\n'.join(full_text_parts)

    
function_map = {
    #common
    "cache": {"function": cache, "input_type": "file_path", "output_type": "file_path","param":"cache_key"},
    "load": {"function": load, "input_type": "any", "output_type": "file_path","param":"cache_key"},
    "save": {"function": save, "input_type": "file_path", "output_type": "file_path","param":"save_key"},
    #ocr
    "tesseract": {"function": tesseract, "input_type": "np_bgr", "output_type": "np_bgr", "param": "lang,config,iter_save"},
}