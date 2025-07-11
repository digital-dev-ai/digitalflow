from airflow import DAG
from airflow.decorators import task, task_group
from datetime import datetime
from tasks.class_create_task import balance_false_images, build_balanced_dataset, train_lilt, image_data_augment
from tasks.file_task import get_file_info_list_task, copy_results_folder_task
from tasks.setup_task import setup_runtime, check_file_exists, setup_target_file_list, end_runtime
from tasks.img_preprocess_task import img_preprocess_task
from airflow.models import Variable,XCom
from utils.com import file_util


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
UPLOAD_IMAGE_DIR = f"{DATA_DIR}/upload/jj" # 테스트 폴더
AREA_SEPARATION_IMAGE_DIR = f"{DATA_DIR}/class/a_class/ocr"
OUTPUT_MODEL_DIR = f"{DATA_DIR}/class/a_class/classify/model"   #ai 모델

with DAG(
    dag_id='lilt_document_area_separation_V0.1',
    start_date=datetime(2024, 1, 1),
    schedule=None,  # None으로 설정하면 수동 트리거만 가능
    catchup=False,
    tags=['document', 'area_separation', 'balanced']
) as dag:
    class_create_init_task = setup_runtime()
    # 1. 진행할 파일 목록 가져오기
    preprced_file_info_list_task = get_file_info_list_task(UPLOAD_IMAGE_DIR)
    # 2. 처리 영역 목록 가져오기
    area_list = file_util.get_config("a_class", "ocr", "area_list")
    # 3. 동적 전처리 및 파이프라인 생성 (해당 루프는 각 area 설정에 대해 별도의 Airflow 태스크 파이프라인을 생성)
    for area_info in area_list:
        # area_name을 사용하여 태스크와 결과물 구분
        area_name = area_info.get("area_name", f"unknown_area_{area_list.index(area_info)}")
        # 해당 영역에 대한 전처리(img_preprocess) 설정 정보 가져옴
        step_preprocess_info = area_info["img_preprocess"]
        # 각 영역별 파이프라인에 고유한 태스크 ID 부여
        preprocess_task_id = f"preprocess_{area_name}"
        copy_task_id = f"copy_results_{area_name}"

        # 3-1. 전처리 태스크(img_preprocess_task) 설정
        #    - step_info: 현재 area에 대한 전처리 단계 정보
        #    - result_key: 처리 결과를 file_info 딕셔너리에 저장할 때 사용할 고유 키
        sep_preprocess_partial_task = img_preprocess_task.override(task_id=preprocess_task_id).partial(
            step_info=step_preprocess_info,
            target_key="_origin"
        )

        # 3-2. 전처리 태스크 확장(expand)
        #    - preprc_file_info_list_task에서 반환된 모든 파일에 대해 전처리 태스크를 실행
        sep_file_list_task = sep_preprocess_partial_task.expand(file_info=preprced_file_info_list_task)

        # 3-3. 결과 복사 태스크(copy_results_folder_task) 설정
        #    - 각 영역의 결과는 별도의 폴더에 저장
        dest_folder = f"{AREA_SEPARATION_IMAGE_DIR}/{area_name}"

        sep_copy_results_task = copy_results_folder_task.override(task_id=copy_task_id)(
            sep_file_list_task,
            dest_folder=dest_folder,
            target_key="_result"
        )


        # 3-4. 의존성 설정
        #    - 모든 파이프라인은 init -> get_file_list 로부터 시작됩니다.
        class_create_init_task >> preprced_file_info_list_task >> sep_file_list_task >> sep_copy_results_task