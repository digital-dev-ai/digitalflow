from airflow.decorators import task
from pathlib import Path
import shutil, os
from airflow.models import Variable
import uuid, json

from utils.db import dococr_query_util
from utils.com import file_util

TEMP_FOLDER = Variable.get("TEMP_FOLDER", default_var="/opt/airflow/data/temp")
RESULT_FOLDER = Variable.get("RESULT_FOLDER", default_var="/opt/airflow/data/result")
OCR_DEBUG_FOLDER = Variable.get("OCR_DEBUG_FOLDER", default_var="/opt/airflow/data/ocr_debug")
OCR_RESULT_FOLDER = Variable.get("OCR_RESULT_FOLDER", default_var="/opt/airflow/data/class/a_class/ocr")

#dag_id = 순환하지 않는 방향성있는 그래프로 표현한 워크플로우의 관리번호(속성: dag소스, 스케쥴 등)
#run_id = dag의 워크플로우에 따른 실행 인스턴스 관리번호(속성: 시작일시, 종료일시, 실행상태 등)
#task_id = 워크플로우의 개별 작업 단위(속성: task소스, 파라미터, 로그 등)
#target_id = 실행 인스턴스에서 동적으로 생성하여 작업할 대상 관리번호(속성: 파일경로, 클래스명, 전처리결과 등)
@task
def setup_runtime(**context):
    dag_id = context['dag'].dag_id
    run_id = context['dag_run'].run_id
    print(f"dag_id: {dag_id}")
    print(f"run_id: {run_id}")
    dococr_query_util.insert_map("insertRun",params=(dag_id,run_id))
    folder = Path(TEMP_FOLDER) / run_id
    folder.mkdir(parents=True, exist_ok=True)
    #캐시 폴더는 수동 삭제하는 것으로 결정.

    # debug_run_folder = Path(OCR_DEBUG_FOLDER) / run_id
    # if debug_run_folder.exists() and debug_run_folder.is_dir():
    #     shutil.rmtree(debug_run_folder)
    # debug_run_folder.mkdir(parents=True, exist_ok=True)
    # print(f"초기화된 디버그 폴더: {debug_run_folder}")

    # --- OCR 결과 폴더 초기화 로직 추가 ---
    # b_class의 각 영역별 results 폴더를 DAG 실행 시마다 초기화합니다.
    # 이렇게 하면 이전 실행에서 남은 .json 파일이 다음 실행에 영향을 주는 것을 방지합니다.
    ocr_b_class_path = Path(OCR_RESULT_FOLDER)
    b_class_ocr_config = file_util.get_config("general_building_register","a_class", "ocr")

    if ocr_b_class_path.is_dir() and b_class_ocr_config and 'area_list' in b_class_ocr_config:
        print(f"'{ocr_b_class_path}' 경로의 OCR 결과 폴더 초기화를 시작합니다.")
        for area_info in b_class_ocr_config['area_list']:
            area_name = area_info.get("area_name")
            if area_name:
                # 예: /opt/airflow/data/class/b_class/ocr/building_info/results
                results_dir = ocr_b_class_path / area_name / "results"
                if results_dir.exists() and results_dir.is_dir():
                    shutil.rmtree(results_dir)
                    print(f"폴더 삭제 완료: {results_dir}")
#폴더 안에 파일이 있는지 분기 있으면 setup_target_file_list, 없으면 no_file_task
@task.branch
def check_file_exists(folder_path):
    p = Path(folder_path)
    for f in p.rglob("*"):
        if f.is_file():
            return "setup_target_file_list"
    return "end_runtime"

from pdf2image import convert_from_path
@task
def setup_target_file_list(folder_path:str,**context):
    run_id = context['dag_run'].run_id
    p = Path(folder_path)
    doc_name = "general_building_register"
    layout_name = "a_class"
    default_doc_class_id = "5"
    default_layout_class_id = "9"
    files = [f for f in p.rglob("*") if f.is_file()]
    file_info_list = []
    db_params_list = []
    for file_path in files:
        id = str(uuid.uuid4())
        if file_path.suffix.lower() == '.pdf':
            path_str = str(file_path)
            file_name = file_path.stem
            images = convert_from_path(path_str, dpi=300)
            output_folder = Path(TEMP_FOLDER) / run_id
            for i, image in enumerate(images):
                page_num = i+1
                img_file_path = os.path.join(output_folder, f'{file_name}_page_{page_num}.png')
                image.save(img_file_path, 'PNG')
                content = {
                    "file_id": id,
                    "page_num": page_num,
                    "file_path": {"_origin": img_file_path, "_origindoc": path_str},
                    "layout_class_id": default_layout_class_id,
                    "doc_class_id": default_doc_class_id
                }
                file_info_list.append(content)
                db_params_list.append((run_id, id, json.dumps(content)))                
        else:
            content = {
                "file_id":id, 
                "page_num":1, 
                "file_path":{"_origin":str(file_path)}, 
                "layout_class_id":default_layout_class_id,
                "doc_class_id": default_doc_class_id
            }
            file_info_list.append(content)
            db_params_list.append( (run_id,id,json.dumps(content)) )
    dococr_query_util.insert_map("insertTargetFile", params=db_params_list)
    return file_info_list

# 이전 타스크가 일부만 성공한 경우엔 중단된 파일정보를 제거 후 다음 타스크로 넘김.
# 반복 사용을 위해 status는 제거.
@task(trigger_rule="all_done")
def remove_failed_results(preprocess_results:list[dict]):
    # 성공한 결과만 필터링하여 다음 단계로 넘김
    if preprocess_results is None:
        return []
    result_only_success = []
    for r in preprocess_results:
        if r and r.get("status") == "success":
            r.pop("status", None)  # status 키 제거
            result_only_success.append(r)
    return result_only_success



@task
def end_runtime(msg="dag을 종료합니다.",**context):
    print(msg)
    dag_id = context['dag'].dag_id
    run_id = context['dag_run'].run_id
    dococr_query_util.update_map("updateRunEnd",params=(dag_id,run_id))
    return