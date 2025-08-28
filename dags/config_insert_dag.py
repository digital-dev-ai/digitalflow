import json
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from airflow import DAG
from datetime import datetime

from utils.db.maria_util import execute  

def upload_layout_to_variables(**context):
    # 1. DB에서 row 가져오기
    query = """
        SELECT IMG_PREPROCESS_INFO, CLASSIFY_AI_INFO
        FROM TB_DI_LAYOUT_CLASS
        WHERE LAYOUT_CLASS_ID = %s
    """
    row = execute(query, params=(9,), fetch=True, dictionary=True)
    
    if not row:
        raise ValueError("No record found for LAYOUT_CLASS_ID=9")
    
    row = row[0]

    # 2. JSON 파싱
    img_preprocess_info_dict = json.loads(row["IMG_PREPROCESS_INFO"])
    classify_ai_info_dict = json.loads(row["CLASSIFY_AI_INFO"])

    # 3. Airflow Variables에 업로드
    Variable.set("IMG_PREPROCESS_INFO", img_preprocess_info_dict)
    Variable.set("CLASSIFY_AI_INFO", classify_ai_info_dict)
    print("✅ Uploaded layout settings to Airflow Variables")

def upload_section_to_variables(**context):
    # 1. DB에서 row 가져오기
    query = """
        SELECT SEPARATE_AREA_INFO, SEPARATE_BLOCK_INFO, OCR_INFO, CLEANSING_INFO
        FROM TB_DI_SECTION_CLASS
        WHERE LAYOUT_CLASS_ID = %s
    """
    rows = execute(query, params=(9,), fetch=True, dictionary=True)
    
    if not rows:
        raise ValueError("No sections found for LAYOUT_CLASS_ID=9")

    # 2. 각 컬럼별 JSON 변환 후 저장
    area_info_list = [json.loads(r["SEPARATE_AREA_INFO"]) for r in rows if r["SEPARATE_AREA_INFO"]]
    block_info_list = [json.loads(r["SEPARATE_BLOCK_INFO"]) for r in rows if r["SEPARATE_BLOCK_INFO"]]
    ocr_info_list = [json.loads(r["OCR_INFO"]) for r in rows if r["OCR_INFO"]]
    cleansing_info_list = [json.loads(r["CLEANSING_INFO"]) for r in rows if r["CLEANSING_INFO"]]

    Variable.set("SECTION_SEPARATE_AREA_INFO", area_info_list)
    Variable.set("SECTION_SEPARATE_BLOCK_INFO", block_info_list)
    Variable.set("SECTION_OCR_INFO", ocr_info_list)
    Variable.set("SECTION_CLEANSING_INFO", cleansing_info_list)
    
    print("✅ Uploaded section settings to Airflow Variables")

with DAG(
    dag_id="config_insert",
    start_date=datetime(2025, 8, 1),
    schedule_interval=None,
    catchup=False,
) as dag:

    upload_layout_task = PythonOperator(
        task_id="upload_layout_settings",
        python_callable=upload_layout_to_variables,
        provide_context=True,
    )

    upload_section_task = PythonOperator(
        task_id="upload_section_settings",
        python_callable=upload_section_to_variables,
        provide_context=True,
    )

    # 순서 지정: layout -> section
    upload_layout_task >> upload_section_task