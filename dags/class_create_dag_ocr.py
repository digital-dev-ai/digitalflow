from airflow import DAG
from datetime import datetime
from pathlib import Path
from tasks.setup_task import setup_runtime, setup_target_file_list
from tasks.file_task import save_ocr_json_task
from tasks.ocr_task import ocr_dispatcher_task
from airflow.models import Variable
from utils.com import file_util
import json

# OCR 대상이 되는, 영역별로 분리된 이미지들이 저장된 기본 폴더
AREA_SEPARATION_IMAGE_DIR = Variable.get("AREA_SEPARATION_IMAGE_DIR", default_var="/opt/airflow/data/class/a_class/ocr")

with DAG(
    dag_id='document_ocr_v1',
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=['ocr', 'document']
) as dag:
    # 1. DAG 실행을 위한 기본 설정
    t_setup_runtime = setup_runtime()

    # 2. 처리할 OCR 영역 목록을 설정 파일에서 가져오기
    # 'b_class'는 예시이며, 필요에 따라 다른 클래스 이름으로 변경할 수 있습니다.
    area_list = file_util.get_config("general_building_register","a_class", "ocr", "area_list")

    # 3. 각 영역별로 동적 파이프라인 생성
    for area_info in area_list:
        area_name = area_info.get("area_name", f"unknown_area_{area_list.index(area_info)}")
        
        # 3-1. 해당 영역의 이미지 파일 목록 가져오기
        area_folder_path = f"{AREA_SEPARATION_IMAGE_DIR}/{area_name}"
        
        # setup_target_file_list를 사용하여 각 파일에 대한 file_info 리스트를 생성합니다.
        t_get_file_list = setup_target_file_list.override(task_id=f"get_files_{area_name}")(
            folder_path=area_folder_path
        )

        # 3-2. OCR 태스크 설정 (partial + expand)
        #    - area_info를 고정하여 각 파일에 대해 동일한 영역 설정을 적용합니다.
        ocr_partial_task = ocr_dispatcher_task.override(task_id=f"ocr_{area_name}").partial(
            area_info=area_info
        )
        
        #    - 파일 목록을 expand하여 병렬로 OCR을 수행합니다.
        ocr_expanded_task = ocr_partial_task.expand(file_info=t_get_file_list)

        # 3-3. OCR 결과를 텍스트 파일로 저장하는 태스크
        #      결과 파일은 각 영역 폴더 아래 'results' 폴더에 저장됩니다.
        result_dest_folder = f"{area_folder_path}/results"
        save_results_partial_task = save_ocr_json_task.override(
            task_id=f"save_ocr_results_{area_name}"
        ).partial(
            dest_folder=result_dest_folder,
            area_name=area_name
        )
        save_results_expanded_task = save_results_partial_task.expand(file_info=ocr_expanded_task)

        # 3-4. 의존성 설정
        t_setup_runtime >> t_get_file_list >> ocr_expanded_task >> save_results_expanded_task