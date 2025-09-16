from PIL import Image
from pathlib import Path
import uuid, os
import numpy as np
import cv2
from airflow.models import Variable
from airflow.operators.python import get_current_context
from typing import Any

TEMP_FOLDER = Variable.get("TEMP_FOLDER", default_var="/opt/airflow/data/temp")
DATA_FOLDER = Variable.get("DATA_FOLDER", default_var="/opt/airflow/data")
BASE_URL = Variable.get("BASE_URL", default_var="http://192.168.10.18:9191")
file_type = ["file_path", "pil", "np_bgr", "np_rgb", "np_gray", "url"]

def convert_type(data: Any, from_type: str, to_type: str, params: dict = None) -> Any:
    """
    데이터를 원하는 타입으로 변경
    input과 output이 명확할 때만 사용할 것
    """
    if to_type=="any":
        return data
    key = (from_type, to_type)
    if key not in type_convert_map:
        raise ValueError(f"변환 불가: {from_type} -> {to_type}")
    func_info = type_convert_map[key]
    return _call_with_compatible_args(func_info, data, params)

#실제 변환 함수
#file_to
def file_to_pil(_file_path: str) -> Image.Image:
    img = Image.open(_file_path)
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img

def file_to_np_bgr(_file_path: str) -> np.ndarray:
    return cv2.imread(_file_path)

def file_to_np_rgb(_file_path: str) -> np.ndarray:
    img = Image.open(_file_path)
    return np.array(img)

def file_to_np_gray(_file_path: str) -> np.ndarray:
    # cv2.IMREAD_GRAYSCALE 옵션으로 2D ndarray 반환
    img = cv2.imread(_file_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"{_file_path} 파일을 찾을 수 없습니다.")
    return img

def file_to_url(_file_path: str) -> str:
    relative_path = os.path.relpath(_file_path, DATA_FOLDER)
    url = f"{BASE_URL}/exstatic/{relative_path.replace(os.sep, '/')}"
    return url


#pil_to
def pil_to_file(_img: Image.Image, file_path: str = None) -> str:
    file_path = _get_file_path(file_path)
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    _img.save(file_path)
    return file_path

def pil_to_np_bgr(_img: Image.Image) -> np.ndarray:
    if _img.mode != "RGB":
        _img = _img.convert("RGB")
    np_img = np.array(_img)
    return cv2.cvtColor(np_img, cv2.COLOR_RGB2BGR)

def pil_to_np_rgb(_img: Image.Image) -> np.ndarray:
    if _img.mode != "RGB":
        _img = _img.convert("RGB")
    return np.array(_img)

def pil_to_np_gray(_img: Image.Image) -> np.ndarray:
    # PIL 이미지를 그레이스케일로 변환 후 numpy로
    if _img.mode != "L":
        _img = _img.convert("L")
    return np.array(_img)

def pil_to_url(_img: Image.Image) -> str:
    file_path = pil_to_file(_img)
    relative_path = os.path.relpath(file_path, DATA_FOLDER)
    url = f"{BASE_URL}/exstatic/{relative_path.replace(os.sep, '/')}"
    return url


#np_bgr_to
def np_bgr_to_file(_img: np.ndarray, file_path: str = None) -> str:
    return _np_to_file(_img,file_path)

def np_bgr_to_pil(_img: np.ndarray) -> Image.Image:
    rgb_img = cv2.cvtColor(_img, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb_img)

def np_bgr_to_np_rgb(_img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(_img, cv2.COLOR_BGR2RGB)

def np_bgr_to_np_gray(_img: np.ndarray) -> np.ndarray:
    # BGR 3채널 이미지를 그레이스케일로 변환
    return cv2.cvtColor(_img, cv2.COLOR_BGR2GRAY)

def np_bgr_to_url(_img: np.ndarray) -> str:
    file_path = np_bgr_to_file(_img)
    relative_path = os.path.relpath(file_path, DATA_FOLDER)
    url = f"{BASE_URL}/exstatic/{relative_path.replace(os.sep, '/')}"
    return url


#np_rgb_to
def np_rgb_to_file(_img: np.ndarray, file_path: str = None) -> str:
    bgr_img = cv2.cvtColor(_img, cv2.COLOR_RGB2BGR)
    return _np_to_file(bgr_img, file_path)

def np_rgb_to_pil(_img: np.ndarray) -> Image.Image:
    pil_img = Image.fromarray(_img)
    if pil_img.mode != "RGB":
        pil_img = pil_img.convert("RGB")
    return pil_img

def np_rgb_to_np_bgr(_img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(_img, cv2.COLOR_RGB2BGR)

def np_rgb_to_np_gray(_img: np.ndarray) -> np.ndarray:
    # RGB 3채널 이미지를 그레이스케일로 변환
    return cv2.cvtColor(_img, cv2.COLOR_RGB2GRAY)

def np_rgb_to_url(_img: np.ndarray) -> str:
    file_path = np_rgb_to_file(_img)
    relative_path = os.path.relpath(file_path, DATA_FOLDER)
    url = f"{BASE_URL}/exstatic/{relative_path.replace(os.sep, '/')}"
    return url


#np_gray_to
def np_gray_to_file(_img: np.ndarray, file_path: str = None) -> str:
    # numpy 2D 배열을 파일로 변환
    return _np_to_file(_img, file_path)

def np_gray_to_pil(_img: np.ndarray) -> Image.Image:
    # numpy 2D 배열을 PIL 이미지로 변환
    pil_img = Image.fromarray(_img)
    pil_img = pil_img.convert("RGB")
    return pil_img

def np_gray_to_np_bgr(_img: np.ndarray) -> np.ndarray:
    # 그레이스케일 이미지를 BGR 3채널로 변환
    return cv2.cvtColor(_img, cv2.COLOR_GRAY2BGR)

def np_gray_to_np_rgb(_img: np.ndarray) -> np.ndarray:
    # 그레이스케일 이미지를 RGB 3채널로 변환
    return cv2.cvtColor(_img, cv2.COLOR_GRAY2RGB)

def np_gray_to_url(_img: np.ndarray) -> str:
    file_path = np_gray_to_file(_img)
    relative_path = os.path.relpath(file_path, DATA_FOLDER)
    url = f"{BASE_URL}/exstatic/{relative_path.replace(os.sep, '/')}"
    return url


def _external_url(_url: str):
    raise ValueError(f"내부 URL이 아닙니다: {_url}")


def _url_to_file(_url: str) -> str:
    prefix = f"{BASE_URL}/exstatic/"
    if not _url.startswith(prefix):
        file_path = _external_url(_url)
    else:
        relative_url = _url[len(prefix):]
        # 상대경로 구분자를 OS 경로 구분자로 변경
        relative_path = relative_url.replace('/', os.sep)
        file_path = os.path.join(DATA_FOLDER, relative_path)
    return file_path


#url_to
def url_to_file(_url: str) -> str:
    return _url_to_file(_url)

def url_to_pil(_url: str) -> Image.Image:
    file_path = _url_to_file(_url)
    return file_to_pil(file_path)

def url_to_np_bgr(_url: str) -> np.ndarray:
    file_path = _url_to_file(_url)
    return file_to_np_bgr(file_path)

def url_to_np_rgb(_url: str) -> np.ndarray:
    file_path = _url_to_file(_url)
    return file_to_np_rgb(file_path)

def url_to_np_gray(_url: str) -> np.ndarray:
    file_path = _url_to_file(_url)
    return file_to_np_gray(file_path)




type_convert_map = {
    # file_path 관련 변환
    (file_type[0], file_type[0]): {"func": lambda x: x, "required_kwargs": [], "optional_kwargs": []},
    (file_type[0], file_type[1]): {"func": file_to_pil, "required_kwargs": [], "optional_kwargs": []},
    (file_type[0], file_type[2]): {"func": file_to_np_bgr, "required_kwargs": [], "optional_kwargs": []},
    (file_type[0], file_type[3]): {"func": file_to_np_rgb, "required_kwargs": [], "optional_kwargs": []},
    (file_type[0], file_type[4]): {"func": file_to_np_gray, "required_kwargs": [], "optional_kwargs": []},
    (file_type[0], file_type[5]): {"func": file_to_url, "required_kwargs": [], "optional_kwargs": []},

    # pil 관련 변환
    (file_type[1], file_type[0]): {"func": pil_to_file, "required_kwargs": [], "optional_kwargs": ["file_path"]},
    (file_type[1], file_type[1]): {"func": lambda x: x, "required_kwargs": [], "optional_kwargs": []},
    (file_type[1], file_type[2]): {"func": pil_to_np_bgr, "required_kwargs": [], "optional_kwargs": []},
    (file_type[1], file_type[3]): {"func": pil_to_np_rgb, "required_kwargs": [], "optional_kwargs": []},
    (file_type[1], file_type[4]): {"func": pil_to_np_gray, "required_kwargs": [], "optional_kwargs": []},
    (file_type[1], file_type[5]): {"func": pil_to_url, "required_kwargs": [], "optional_kwargs": []},

    # np_bgr 관련 변환
    (file_type[2], file_type[0]): {"func": np_bgr_to_file, "required_kwargs": [], "optional_kwargs": ["file_path"]},
    (file_type[2], file_type[1]): {"func": np_bgr_to_pil, "required_kwargs": [], "optional_kwargs": []},
    (file_type[2], file_type[2]): {"func": lambda x: x, "required_kwargs": [], "optional_kwargs": []},
    (file_type[2], file_type[3]): {"func": np_bgr_to_np_rgb, "required_kwargs": [], "optional_kwargs": []},
    (file_type[2], file_type[4]): {"func": np_bgr_to_np_gray, "required_kwargs": [], "optional_kwargs": []},
    (file_type[2], file_type[5]): {"func": np_bgr_to_url, "required_kwargs": [], "optional_kwargs": []},

    # np_rgb 관련 변환
    (file_type[3], file_type[0]): {"func": np_rgb_to_file, "required_kwargs": [], "optional_kwargs": ["file_path"]},
    (file_type[3], file_type[1]): {"func": np_rgb_to_pil, "required_kwargs": [], "optional_kwargs": []},
    (file_type[3], file_type[2]): {"func": np_rgb_to_np_bgr, "required_kwargs": [], "optional_kwargs": []},
    (file_type[3], file_type[3]): {"func": lambda x: x, "required_kwargs": [], "optional_kwargs": []},
    (file_type[3], file_type[4]): {"func": np_rgb_to_np_gray, "required_kwargs": [], "optional_kwargs": []},
    (file_type[3], file_type[5]): {"func": np_rgb_to_url, "required_kwargs": [], "optional_kwargs": []},

    # np_gray 관련 변환
    (file_type[4], file_type[0]): {"func": np_gray_to_file, "required_kwargs": [], "optional_kwargs": ["file_path"]},
    (file_type[4], file_type[1]): {"func": np_gray_to_pil, "required_kwargs": [], "optional_kwargs": []},
    (file_type[4], file_type[2]): {"func": np_gray_to_np_bgr, "required_kwargs": [], "optional_kwargs": []},
    (file_type[4], file_type[3]): {"func": np_gray_to_np_rgb, "required_kwargs": [], "optional_kwargs": []},
    (file_type[4], file_type[4]): {"func": lambda x: x, "required_kwargs": [], "optional_kwargs": []},
    (file_type[4], file_type[5]): {"func": np_gray_to_url, "required_kwargs": [], "optional_kwargs": []},

    # url 관련 변환
    (file_type[5], file_type[0]): {"func": url_to_file, "required_kwargs": [], "optional_kwargs": []},
    (file_type[5], file_type[1]): {"func": url_to_pil, "required_kwargs": [], "optional_kwargs": []},
    (file_type[5], file_type[2]): {"func": url_to_np_bgr, "required_kwargs": [], "optional_kwargs": []},
    (file_type[5], file_type[3]): {"func": url_to_np_rgb, "required_kwargs": [], "optional_kwargs": []},
    (file_type[5], file_type[4]): {"func": url_to_np_gray, "required_kwargs": [], "optional_kwargs": []},
    (file_type[5], file_type[5]): {"func": lambda x: x, "required_kwargs": [], "optional_kwargs": []},
}


#내부함수
def _np_to_file(_img: np.ndarray, file_path: str = None) -> str:
    file_path = _get_file_path(file_path)
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    status = cv2.imwrite(file_path, _img)
    if not status:
        print("img shape:", _img.shape if _img is not None else None)
        print("img dtype:", _img.dtype if _img is not None else None)
        raise ValueError(f"파일 생성이 실패하였습니다. {file_path}")
    return file_path


def _get_file_path(file_path: str = None) -> str:
    if file_path is not None:
        return file_path
    else:
        context = get_current_context()
        if context:
            return str(Path(TEMP_FOLDER) / context["run_id"] / f"{uuid.uuid4()}.png")
        else:
            return str(Path(TEMP_FOLDER) / f"{uuid.uuid4()}.png")


def _call_with_compatible_args(func_info, data, params: dict):
    """
    func_info는 dict 형태로 func, required_kwargs, optional_kwargs 저장
    params: dict로 추가 인자 전달
    data는 항상 첫 번째 인자로 전달
    """
    f = func_info["func"]
    call_args = {}
    if params is None:
        params = {}
    
    # 필수 인자 체크
    for req_arg in func_info.get("required_kwargs", []):
        if req_arg not in params:
            raise ValueError(f"필수 인자 {req_arg}가 누락되었습니다.")
        call_args[req_arg] = params[req_arg]

    # 선택적 인자 체크
    for opt_arg in func_info.get("optional_kwargs", []):
        if opt_arg in params:
            call_args[opt_arg] = params[opt_arg]

    # 첫 번째 인자(data)는 항상 전달
    return f(data, **call_args)
