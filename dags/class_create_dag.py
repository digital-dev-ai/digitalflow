from airflow import DAG
from airflow.decorators import task, task_group
from datetime import datetime
from tasks.class_create_task import balance_false_images, build_balanced_dataset, train_lilt, image_data_augment
from tasks.file_task import get_file_info_list_task, copy_results_folder_task
from tasks.init_task import init_task
from tasks.img_preprocess_task import img_preprocess_task
from airflow.models import Variable,XCom
from utils import file_util


NONE_DOC_IMAGE_DIR = Variable.get("NONE_CLASS_FOLDER", default_var="/opt/airflow/data/none_class") # 비서식 일반 문서 이미지
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
OUTPUT_MODEL_DIR = f"{DATA_DIR}/class/a_class/classify/model"   #ai 모델

with DAG(
    dag_id='lilt_document_classifier_balanced_V0.1',
    start_date=datetime(2024, 1, 1),
    schedule=None,  # None으로 설정하면 수동 트리거만 가능
    catchup=False,
    tags=['document', 'classification', 'balanced']
) as dag:
    class_create_init_task = init_task()
    # 증강 처리
    image_data_augment_task = image_data_augment(ORIGIN_TRUE_IMAGE_DIR,READY_TRUE_IMAGE_DIR)
    # true 파일에 따라 false 파일 채우기
    balance_result_task = balance_false_images(READY_IMAGE_DIR)
    
    #스텝정보 가져오기
    a_class_classify_preprocess_info = file_util.get_step_info_list("a_class","classify","img_preprocess")

    true_file_info_list_task = get_file_info_list_task(READY_TRUE_IMAGE_DIR)
    true_file_preprocess_partial_task = img_preprocess_task.partial(step_info=a_class_classify_preprocess_info,result_key="true")
    true_file_list_task = true_file_preprocess_partial_task.expand(file_info=true_file_info_list_task)
    true_copy_results_task = copy_results_folder_task(true_file_list_task,dest_folder=PREPRC_TRUE_IMAGE_DIR,result_key="true")
    
    false_file_info_list_task = get_file_info_list_task(READY_FALSE_IMAGE_DIR)
    false_file_preprocess_partial_task = img_preprocess_task.partial(step_info=a_class_classify_preprocess_info,result_key="false")
    false_file_list_task = false_file_preprocess_partial_task.expand(file_info=false_file_info_list_task)
    false_copy_results_task = copy_results_folder_task(false_file_list_task,dest_folder=PREPRC_FALSE_IMAGE_DIR,result_key="false")

    # 3. 균형이 맞춰진 데이터셋 구성
    #dataset = build_balanced_dataset(PREPRC_IMAGE_DIR)

    # 4. 모델 학습
    #train = train_lilt(dataset,OUTPUT_MODEL_DIR)
    
    class_create_init_task >> image_data_augment_task
    image_data_augment_task >> balance_result_task >> [true_file_info_list_task, false_file_info_list_task]
    true_file_info_list_task >> true_file_list_task >> true_copy_results_task
    false_file_info_list_task >> false_file_list_task >> false_copy_results_task
    #[true_copy_results_task,false_copy_results_task] >> dataset >> train
    # image_data_augment_task >> balance_result_task >> dataset >> train