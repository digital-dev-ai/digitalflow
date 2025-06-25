from airflow import DAG
from airflow.decorators import task, task_group
from datetime import datetime

from tasks.class_create_task import balance_false_images, build_balanced_dataset, train_lilt, image_data_augment
from tasks.file_task import get_file_info_list_task, copy_results_folder_task
from tasks.init_task import init_task
from tasks.img_preprocess_task import img_preprocess_task

# 경로 설정 (DAG 파라미터로 받거나 환경변수로 설정 가능)
DATA_DIR = "/opt/airflow/data"   # 루트
ORIGIN_IMAGE_DIR = f"{DATA_DIR}/class/a_class/classify/origin"   # 원본 문서 이미지
ORIGIN_TRUE_IMAGE_DIR = f"{ORIGIN_IMAGE_DIR}/true"   # 특정 서식 원본 문서 이미지
ORIGIN_FALSE_IMAGE_DIR = f"{ORIGIN_IMAGE_DIR}/false" # 일반 문서 이미지
READY_IMAGE_DIR = f"{DATA_DIR}/class/a_class/classify/ready"   # 증강 문서 이미지
READY_TRUE_IMAGE_DIR = f"{READY_IMAGE_DIR}/true"   # 특정 서식 증강된 문서 이미지
READY_FALSE_IMAGE_DIR = f"{READY_IMAGE_DIR}/false" # 일반 증강된 문서 이미지
PREPRC_IMAGE_DIR = f"{DATA_DIR}/class/a_class/classify/preprc"   # 전처리된 문서 이미지
PREPRC_TRUE_IMAGE_DIR = f"{PREPRC_IMAGE_DIR}/true"   # 특정 서식 전처리된 문서 이미지
PREPRC_FALSE_IMAGE_DIR = f"{PREPRC_IMAGE_DIR}/false" # 일반 전처리된 문서 이미지
NONE_DOC_IMAGE_DIR = f"{DATA_DIR}/none_class" # 비서식 일반 문서 이미지
OUTPUT_MODEL_DIR = f"{DATA_DIR}/class/a_class/classify/model"   #ai 모델

with DAG(
    dag_id='lilt_document_classifier_balanced_no_preprc_V0.1',
    start_date=datetime(2024, 1, 1),
    schedule=None,  # None으로 설정하면 수동 트리거만 가능
    catchup=False,
    tags=['document', 'classification', 'balanced']
) as dag:
    class_create_init_task = init_task()
    # 3. 균형이 맞춰진 데이터셋 구성
    dataset = build_balanced_dataset(PREPRC_IMAGE_DIR)

    # 4. 모델 학습
    train = train_lilt(dataset,OUTPUT_MODEL_DIR)
    
    class_create_init_task >> dataset >> train
    # image_data_augment_task >> balance_result_task >> dataset >> train