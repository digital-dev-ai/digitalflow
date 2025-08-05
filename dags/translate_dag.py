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
from tasks.translate_output_task import translate_output_task

TEMP_FOLDER = Variable.get("TEMP_FOLDER", default_var="/opt/airflow/data/temp")
RESULT_FOLDER = Variable.get("RESULT_FOLDER", default_var="/opt/airflow/data/upload")
UPLOAD_FOLDER = Variable.get("UPLOAD_FOLDER", default_var="/opt/airflow/data/upload")

# DAG 정의 (DAG 클래스 직접 사용)
with DAG(
    dag_id="translate_v1", # 이전 DAG ID와 충돌 방지를 위해 변경
    start_date=datetime(2024, 1, 1),
    schedule=None, # None으로 설정하면 수동 트리거만 가능
    catchup=False,
    tags=['image', 'batch']
) as dag:
    table_info = [{
            "table_name": "TB_OCR_BILD_BASIC_INFO",
            "id_col_name": "BILD_SEQ_NUM"
        },
        {
            "table_name": "TB_OCR_FLR_STATUS",
            "id_col_name": "FLR_SEQ_NUM"
        },
        {
            "table_name": "TB_OCR_OWN_STATUS",
            "id_col_name": "OWNR_SEQ_NUM"
        },
    ]
    t_translate_output = translate_output_task.expand(table_info=table_info)
