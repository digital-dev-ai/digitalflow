from airflow.decorators import task
from pathlib import Path
import shutil, os, json
from airflow.models import Variable

TEMP_FOLDER = Variable.get("TEMP_FOLDER", default_var="/opt/airflow/data/temp")
RESULT_FOLDER = Variable.get("RESULT_FOLDER", default_var="/opt/airflow/data/result")

def get_step_info_list(*keys):
    class_map = {
        "a_class":{
            "class_id":1111,
            "classify":{
                "classify_id":1111,
                "classify_ai":{
                    "ai_id":15,
                    "ai_dir":"/opt/airflow/data/class/a_class/classify/model",
                    "processor_name":"SCUT-DLVCLab/lilt-roberta-en-base",
                    "model_name":"SCUT-DLVCLab/lilt-roberta-en-base",
                },
                "img_preprocess":{
                    "name":"a_class classify img_preprc",
                    "type":"step_list",
                    "step_list":[
                        {"name":"cache","param":{"cache_key":"origin"}},
                        {"name":"calc_angle_set2","param":{"angle_key":"angle2_1","delta":8.0,"limit":40,"iterations":2,"iter_save":False}},
                        {"name":"calc_angle_set2","param":{"angle_key":"angle2_2","delta":1.0,"limit":8,"iterations":2,"iter_save":False}},
                        {"name":"calc_angle_set2","param":{"angle_key":"angle2_3","delta":0.125,"limit":1,"iterations":2,"iter_save":False}},
                        {"name":"text_orientation_set","param":{"angle_key":"orint","iterations":3,"iter_save":False}},
                        {"name":"load","param":{"cache_key":"origin"}},
                        {"name":"rotate","param":{"angle_keys":["angle2_1","angle2_2","angle2_3","orint"]}},
                        {"name":"del_blank_set1","param":{}},
                    ], 
                }
            },
            "area_cut":{
                "area_id":113,
                "area_cnt":1,
                "area_list":[

                ]
            },
            "ocr":{},
            "save":{
                "save_list":[
                    "classify_preprocess"
                ],
            },
        },
        "b_class":{
            "class_id":1111,
            "classify":{
                "classify_id":1111,
                "classify_ai":{
                    "ai_id":15,
                    "ai_dir":"/opt/airflow/data/class/b_class/classify/model",
                    "processor_name":"SCUT-DLVCLab/lilt-roberta-en-base",
                    "model_name":"SCUT-DLVCLab/lilt-roberta-en-base",
                },
                "img_preprocess":{
                    "name":"b_class classify img_preprc",
                    "type":"step_list",
                    "step_list":[
                        {"name":"cache","param":{"cache_key":"origin"}},
                        {"name":"calc_angle_set2","param":{"angle_key":"angle2_1","delta":8.0,"limit":40,"iterations":2,"iter_save":False}},
                        {"name":"calc_angle_set2","param":{"angle_key":"angle2_2","delta":1,"limit":8,"iterations":2,"iter_save":False}},
                        {"name":"calc_angle_set2","param":{"angle_key":"angle2_3","delta":0.125,"limit":1,"iterations":2,"iter_save":False}},
                        {"name":"text_orientation_set","param":{"angle_key":"orint","iterations":2,"iter_save":False}},
                        {"name":"load","param":{"cache_key":"origin"}},
                        {"name":"rotate","param":{"angle_key":"angle2_1"}},
                        {"name":"rotate","param":{"angle_key":"angle2_2"}},
                        {"name":"rotate","param":{"angle_key":"angle2_3"}},
                        {"name":"rotate","param":{"angle_key":"orint"}},
                    ], 
                }
            },
            "area_cut":{},
            "ocr":{},
            "save":{
                "save_list":[
                    "classify_preprocess"
                ],
            },
        }
    }
    return _get_deep_info(class_map,*keys)

def get_image_paths(directory: str) -> list[str]:
    """해당 폴더의 이미지 경로 리스트 반환"""
    if not os.path.exists(directory):
        return []
    return [os.path.join(directory, f) for f in os.listdir(directory) 
            if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

def get_image_paths_recursive(directory: str) -> list[str]:
    """해당 폴더 하위까지 포함하여 이미지 경로 리스트 반환"""
    image_paths = []
    for root, dirs, files in os.walk(directory):
        for f in files:
            if f.lower().endswith(('.png', '.jpg', '.jpeg')):
                image_paths.append(os.path.join(root, f))
    return image_paths

def file_copy(src_file: str, dest_file: str) -> str:
    """
    파일을 복사하는 함수
    
    :param src_file: 복사할 파일 경로(문자열)
    :param dest_file: 붙여넣을 파일 경로(문자열)
    :return: 실제로 복사된 파일 경로(문자열)
    """
    print("file_copy:",dest_file)
    src = Path(src_file)
    dest = Path(dest_file)

    # 붙여넣을 폴더가 없으면 생성
    dest.parent.mkdir(parents=True, exist_ok=True)

    # 파일명과 확장자 분리
    stem = dest.stem
    suffix = dest.suffix
    count = 1

    # 파일이 이미 존재하면 숫자를 붙여서 복사
    while dest.exists():
        dest = dest.parent / f"{stem}({count}){suffix}"
        count += 1

    # 파일 복사
    shutil.copy2(src, dest)

    return str(dest)

#내부함수
#dict 데이터 값 찾아가기
def _get_deep_info(data, *keys):
    for key in keys:
        if isinstance(data, dict) and key in data:
            data = data[key]
        else:
            return None
    return data
