from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.decorators import task, task_group
from datetime import datetime, timedelta
from pathlib import Path
import os
import json
from airflow.models import Variable, XCom
# utils 모듈 임포트 (PYTHONPATH에 proj
# ect_root가 잡혀있다고 가정)
# 만약 utils 모듈이 DAG 파일과 같은 디렉토리 내에 있다면, 상대 경로 임포트를 고려하거나
# Airflow DAGs 폴더 구조에 맞게 배치해야 합니다.
# 예: dags/your_dag_file.py, dags/utils/file_util.py
from tasks.ocr_task_sjh import ocr_dispatcher_task
from utils.com import file_util
from tasks.file_task import get_file_info_list_task,copy_results_folder_task, clear_temp_folder_task
from tasks.setup_task import setup_runtime, check_file_exists, setup_target_file_list, end_runtime
from tasks.img_preprocess_task import img_preprocess_task

TEMP_FOLDER = Variable.get("TEMP_FOLDER", default_var="/opt/airflow/data/temp")
RESULT_FOLDER = Variable.get("RESULT_FOLDER", default_var="/opt/airflow/data/upload")
UPLOAD_FOLDER = Variable.get("UPLOAD_FOLDER", default_var="/opt/airflow/data/upload")

# DAG 정의 (DAG 클래스 직접 사용)
with DAG(
    dag_id="test_ocr_v1", # 이전 DAG ID와 충돌 방지를 위해 변경
    start_date=datetime(2024, 1, 1),
    schedule=None, # None으로 설정하면 수동 트리거만 가능
    catchup=False,
    tags=['image', 'batch']
) as dag:
    t_test_setup_runtime = setup_runtime()
    
    #A클래스에서 분리된 영역
    STANDARD_FOLDER = "/opt/airflow/data/standard"
    b_check_file_exists = check_file_exists(STANDARD_FOLDER)
    t_no_file_end = end_runtime("폴더 안에 파일이 존재하지 않습니다.")
    t_target_file_info_list = setup_target_file_list(STANDARD_FOLDER)
    
    area_list = file_util.get_config("a_class","ocr","area_list")
    t_ocr_dispatcher_task = ocr_dispatcher_task.partial(area_list=area_list,target_key="_origin").expand(file_info=t_target_file_info_list)
                                                 
    
    #all_clear_temp_folder_task = clear_temp_folder_task()
    # 태스크 간 의존성 설정
    # XCom을 통해 데이터가 전달되므로, 태스크 실행 순서만 정의합니다.
    t_test_setup_runtime>> b_check_file_exists
    b_check_file_exists >> t_no_file_end
    b_check_file_exists >> t_target_file_info_list >> t_ocr_dispatcher_task 
    #t_table_ocr_by_cell >> all_clear_temp_folder_task

if __name__ == "__main__":
    # 현재 Executor가 DebugExecutor인지 확인
    # 1. 환경 변수에서 직접 확인
    current_executor = os.getenv("AIRFLOW__CORE__EXECUTOR", "")
    is_debug_executor = current_executor.lower() == "debugexecutor"
    print(current_executor,is_debug_executor)

    # debugExecutor를 사용하면 dag 디버깅이 가능합니다.
    # 병렬 처리는 안되고 순차적으로 처리됩니다.
    if is_debug_executor:
        from pytz import timezone
        # DebugExecutor 환경에서만 아래 코드 실행
        KST = timezone(timedelta(hours=9))
        start_date = datetime(year=2022, month=5, day=1, hour=21, minute=0, second=0, tzinfo=KST)
        end_date = datetime(year=2022, month=6, day=1, hour=21, minute=0, second=0, tzinfo=KST)

        # 'transform_load' 태스크만 클리어 (실행 전 초기화)
        dag.clear(task_ids=['transform_load'])

        # DAG 실행 (의존성 무시)
        dag.run(start_date=start_date, end_date=end_date, ignore_task_deps=True)
    # Airflow 2.x에서 Python 스크립트 직접 실행 시에는 DAG가 파싱만 됩니다.
    # 실제 테스트는 Airflow CLI를 통해 실행해야 합니다.
    else:
        # 주의: 이 부분은 Airflow 2.x에서는 dag_instance를 직접 호출하여 테스트하는 방식이 아닙니다.
        # DAG 파일은 단순히 Airflow 스케줄러/웹서버가 읽고 파싱할 수 있도록 존재합니다.
        print("이 스크립트를 직접 실행하면 DAG가 Airflow에 로드됩니다.")
        print("DAG를 테스트하려면 Airflow CLI 명령을 사용하세요.")
        print("예: airflow dags test image_processing_per_file_v2 2024-01-01")
