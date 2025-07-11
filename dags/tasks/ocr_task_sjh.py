from airflow.decorators import task
import cv2
import numpy as np
from utils.dev import draw_block_box_util
from utils.ocr import separate_area_util, separate_block_util, ocr_util
from typing import List, Dict, Any

@task
def ocr_dispatcher_task(file_info: Dict, area_list: List, target_key: Dict[str, Any], **context) -> Dict[str, Any]:
    """
    OCR 타입에 따라 적절한 OCR 태스크를 선택하여 실행합니다.
    
    :param file_info: 처리할 파일 정보 딕셔너리
    :param area_info: OCR을 수행할 영역의 설정 정보 (ocr_type 포함)
    :param context: Airflow 컨텍스트 딕셔너리
    :return: OCR 결과가 추가된 file_info 딕셔너리
    """
    # 1. 파일 로딩
    #    - file_info에 저장된 이미지를 원본으로 통칭
    #    - 2번작업으로 잘린 이미지들을 영역으로 통칭
    #    - 3번작업으로 잘린 이미지들을 블록으로 통칭
    #    - 블록맵은 {id:"",cell_box:[x,y,w,h],child:0} 형태로 저장
    #    - (원본이미지,블록맵)을 블록정보로 통칭
    #    - 원본의 블록맵 생성하여 A(가로),B(세로)큐 중 하나에 (원본이미지,블록맵) 입력
    #(area_info 기준 for문 시작)
    # 2. 영역 분할
    #    - 원본의 블록정보에서 area_info에 정의된 정보를 기준으로 영역 추출
    #    - 추출된 영역을 분석하여 블록맵 생성
    #    - 블록정보를 area_info에 설정된 값에 따라 A(가로),B(세로) 큐에 저장
    #(A/B큐 기준 while문 시작)
    # 3. while 루프를 통해 경계선 기준으로 파일 자르기(A큐, B큐)
    #    - 자르기 전 이미지는 부모, 자른 이미지는 자식으로 통칭
    #    - A, B큐의 모든 파일 처리할 때까지 반복
    #    - 플래그를 통해 이번 와일문에서 A큐를 작업할 지 B큐를 작업할지 결정(디폴트 A큐)
    #    (A큐 기준 while문)
    #    - A큐에서 이미지를 뽑아 수평으로 자르기
    #    - 자식id는 부모id + "_h" + n (n은 1부터 시작하는 인덱스)
    #    - 자식 좌표는 부모 좌표를 더하여 원본 기준 좌표로 계산
    #    - 자식 블록정보는 B큐에 입력
    #    - 자르는 작업이 완료된 부모는 child 개수를 추가한 블록정보를 C목록에 저장
    #    - A큐가 비어있으면 플래그를 B큐로 변경
    #    (B큐 기준 while문)
    #    - B큐에서 이미지를 뽑아 수직으로 자르기
    #    - 자식id는 부모id + "_v" + n (n은 1부터 시작하는 인덱스)
    #    - 자식 좌표는 부모 좌표를 더하여 원본 기준 좌표로 계산
    #    - 자식 블록정보는 A큐에 입력
    #    - 자르는 작업이 완료된 부모는 child 개수를 추가한 블록정보를 C목록에 저장
    #    - B큐가 비어있으면 플래그를 A큐로 변경
    #(A/B큐 기준 while문 종료)
    # 4. C목록에서 child 개수가 0인 블록정보를 기준으로 OCR 수행
    #    - 이미지 OCR 수행 후 결과를 블록맵에 ocr로 추가하여 D목록에 저장
    #    - D목록은 (img_np_bgr,{block_id:"tab_v2h3",block_box:[x,y,w,h], child:0, ocr:[{text:"", confidence:0.0}]}) 형태로 저장
    #    - D목록은 A큐, B큐에서 모두 처리된 블록정보를 포함
    #(area_info 기준 for문 종료)
    # 1. 파일 로딩
    original_image = file_info["file_path"][target_key]
    
    # 2. 영역 분할
    for area_info in area_list:
        area_name = area_info["area_name"]
        separate_area_step_info = area_info["separate_area"]
        img_np_bgr,result_map = separate_area_util.separate_area(original_image, data_type="file_path", output_type="np_bgr", step_info=separate_area_step_info)
        area_x, area_y = result_map["_area"]
        print(area_name,"separate_area completed:")
        block_map = {"block_id": area_name, "block_box": [area_x, area_y, img_np_bgr.shape[1], img_np_bgr.shape[0]]}
        block_data = (img_np_bgr,block_map)
        separate_block_step_info = area_info["separate_block"]
        block_list = separate_block_util.separate_block(block_data, input_img_type="np_bgr", output_img_type="np_bgr", step_info=separate_block_step_info)
        print(area_name,"separate_block completed:", len(block_list))
        
        # 4. C목록에서 child==0인 블록정보로 OCR 수행
        ocr_list = []
        draw_block_list = []
        #block_box_list = [item[1]["block_box"] for item in block_list]
        block_box_list = [item[1]["block_box"] for item in block_list if item[1]["child"] == 0]
        draw_block_box_util.draw_block_box_step_list((original_image, block_box_list), input_img_type="file_path", step_list=[{"name": "draw_block_box_xywh", "param": {"box_color": 1, "iter_save": True}}])
        for block_data in block_list:
            block_img_np_bgr, block_map = block_data
            print(area_name,"block_map:", block_map)
            if block_map['child'] == 0:
                ocr_step_info = area_info["ocr"]  
                block_map = ocr_util.ocr((block_img_np_bgr, block_map), input_img_type="np_bgr", step_info=ocr_step_info, result_map={"folder_path":area_name}) # ocr결과가 추가된 block_map 반환
                print("=========",block_map)
                draw_block_list.append(block_map)
                ocr_list.append(block_map)
        
        #draw_block_box_util.draw_block_box_step_list((original_image, draw_block_list), input_img_type="file_path", step_list=[{"name": "draw_block_box_xywh", "param": {"box_color": 1, "iter_save": True}}])
        
        file_info["ocr_results"] = ocr_list

    return file_info
    
def _perform_ocr(img_np_bgr):
    return [
        {
            "text": "Sample OCR Text",
            "box": [10, 20, 100, 50],
            "confidence": 0.95
        }
    ]