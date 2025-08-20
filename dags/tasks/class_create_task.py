from airflow.decorators import task
import os
import cv2
import numpy as np  # np import 추가
from pandas.core.base import np
from torchvision.transforms import InterpolationMode
from utils.ai.machine_learning_dataset import extract_feature_for_table_doc_util
from utils.ocr import separate_area_util  # import 경로 수정
from utils.img import img_preprocess_util
from utils.com import json_util
from utils.com import file_util
from airflow.models import Variable
import torch.nn.functional as F  # 상단에 추가
import random
import shutil
import uuid

RESULT_FOLDER = Variable.get("RESULT_FOLDER", default_var="/opt/airflow/data/result")
TEMP_FOLDER = Variable.get("TEMP_FOLDER", default_var="/opt/airflow/data/temp")
NONE_DOC_IMAGE_DIR = Variable.get("NONE_CLASS_FOLDER", default_var="/opt/airflow/data/common/none_class") # 비서식 일반 문서 이미지

@task(pool='ocr_pool')
def balance_false_images(root_path:str):
    def get_image_count(root_dir):
        """각 디렉토리의 이미지 개수를 계산"""
        true_folder = f"{root_dir}/true"
        false_folder = f"{root_dir}/false"
        true_count = len(file_util.get_image_paths(true_folder))
        false_count = len(file_util.get_image_paths(false_folder))

        none_doc_count = len(file_util.get_image_paths_recursive(NONE_DOC_IMAGE_DIR))
        
        print(f"{root_dir} TRUE 파일 개수: {true_count}")
        print(f"{root_dir} FALSE 파일 개수: {false_count}")
        print(f"NONE_DOC_IMAGE_DIR 파일 개수: {none_doc_count}")
        
        return {
            "true_count": true_count,
            "false_count": false_count,
            "none_doc_count": none_doc_count
        }
    counts_info = get_image_count(root_path)

    false_folder = f"{root_path}/false"
    true_count = counts_info["true_count"]
    false_count = counts_info["false_count"]
    
    needed_files = true_count - false_count
    if needed_files <= 0:
        print(f"FALSE_IMAGE_DIR에 충분한 파일이 있습니다. (필요: {needed_files})")
        return {"copied_count": 0, "total_false_count": false_count}

    none_doc_paths = file_util.get_image_paths_recursive(NONE_DOC_IMAGE_DIR)
    none_doc_count = len(none_doc_paths)

    if needed_files > none_doc_count:
        print(f"경고: 사용 가능 파일 부족 (요청: {needed_files}, 실제: {none_doc_count})")
        needed_files = none_doc_count
        if false_count == 0 and none_doc_count == 0:
            raise ValueError("학습을 위한 최소 데이터가 없습니다")

    # 수정 사항 3: needed_files가 0인 경우 처리
    selected_files = random.sample(none_doc_paths, needed_files) if needed_files > 0 else []
    
    os.makedirs(false_folder, exist_ok=True)
    copied_count = 0
    for src_path in selected_files:
        try:
            filename = os.path.basename(src_path)
            new_filename = f"copied_{copied_count}_{filename}"
            dst_path = os.path.join(false_folder, new_filename)
            shutil.copy2(src_path, dst_path)
            copied_count += 1
            print(f"복사 완료: {src_path} -> {dst_path}")
        except Exception as e:
            print(f"복사 실패: {src_path} - {str(e)}")
    
    return {"copied_count": copied_count, "total_false_count": false_count + copied_count}

@task(pool='ocr_pool') 
def build_balanced_dataset(true_folder:str,false_folder:str):
    """균형이 맞춰진 데이터셋 구성"""
    # true_folder = f"{root_path}/true"
    # false_folder = f"{root_path}/false"
    true_image_paths = file_util.get_image_paths(true_folder)
    false_image_paths = file_util.get_image_paths(false_folder)
    
    dataset = []
    
    # True 라벨 데이터 추가
    for path in true_image_paths:
        dataset.append({"image_path": path, "label": 1})
    
    # False 라벨 데이터 추가
    for path in false_image_paths:
        dataset.append({"image_path": path, "label": 0})
    
    print(f"데이터셋 구성 완료:")
    print(f"- True 라벨: {len(true_image_paths)}개")
    print(f"- False 라벨: {len(false_image_paths)}개")
    print(f"- 총 데이터셋 크기: {len(dataset)}개")
    
    return dataset


@task(pool='ocr_pool')
def train(dataset: list, classify_ai_info: dict, ai_dir="/opt/airflow/data/class/noclass/classify/model/noprc",model_name=None):
    target_processor_name = classify_ai_info.get("processor_name", "ML")
    target_model_name = classify_ai_info.get("model_name", model_name)
    model_dir = classify_ai_info.get("ai_dir",ai_dir)
    class_key = classify_ai_info.get("class_key", "")
    if target_processor_name == "SCUT-DLVCLab/lilt-roberta-en-base":
        return train_lilt(dataset, model_dir, class_key=class_key)
    elif target_processor_name == "ML":
        return train_ml(dataset, model_dir, target_model_name, class_key=class_key)

def train_lilt(dataset: list, model_dir:str, horizontal_kernel_ratio: float = 0.8, vertical_kernel_ratio: float = 0.038, class_key: str = ""):
    """LiLT 경량 모델 학습 및 검증 (메모리 최적화 버전)"""
    import torch
    from torch.utils.data import Dataset, DataLoader, random_split
    from transformers import AutoProcessor, AutoModelForSequenceClassification
    from torch.optim import AdamW
    from PIL import Image
    import pytesseract
    import os

    if not dataset:
        print("데이터셋이 비어있습니다.")
        return

    device = torch.device("cpu")  # CPU로 고정
    torch.set_default_dtype(torch.float32)

    # LiLT 모델 및 프로세서 로드
    processor = AutoProcessor.from_pretrained(
        "SCUT-DLVCLab/lilt-roberta-en-base",
        use_fast=True
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        "SCUT-DLVCLab/lilt-roberta-en-base",
        num_labels=2,
        torch_dtype=torch.float32
    ).to(device)

    class DocDataset(Dataset):
        def __init__(self, data, processor):
            self.data = data
            self.processor = processor

        def __len__(self):
            return len(self.data)

        def __getitem__(self, idx):
            item = self.data[idx]
            image = Image.open(item["image_path"]).convert("RGB")
            image_width, image_height = image.size

            process_id = f"_cc_{str(uuid.uuid4())}"
            # 1. 상단 헤더 영역만 분리하여 OCR 수행
            header_img, _ = separate_area_util.separate_area_step_list(
                image, data_type="pil", output_type="pil",
                step_list=[{"name":"save","param":{"save_key":"_origin","tmp_save":True}},
                    {"name" : "separate_areas_set1", "param": {"area_name":"doc_subject","area_type":"top_center","area_ratio":[-0.083,0.068,0.188,0.068],"iter_save":False}},
                    {"name":"save","param":{"save_key":"_cutted","tmp_save":True}}
                ],
                result_map={"folder_path":process_id}
            )
            # header_img는 PIL.Image 객체
            header_width, header_height = header_img.size
            # 헤더 OCR
            try:
                data = pytesseract.image_to_data(header_img, output_type=pytesseract.Output.DICT, lang='kor+eng', config='--psm 6 --oem 3')
            except Exception as e:
                print(f"OCR error: {e}")
                data = {"text": [], "left": [], "top": [], "width": [], "height": []}
            
            # 1-1. OCR 결과를 lilt 학습을 위햐 변환
            def normalize_bbox(bbox, image_width, image_height):
                x1, y1, x2, y2 = bbox
                x1 = int(1000 * (x1 / image_width))
                y1 = int(1000 * (y1 / image_height))
                x2 = int(1000 * (x2 / image_width))
                y2 = int(1000 * (y2 / image_height))
                return [x1, y1, x2, y2]

            words = []
            boxes = []
            for word, x, y, w, h in zip(data['text'], data['left'], data['top'], data['width'], data['height']):
                if word.strip():
                    words.append(word.strip())
                    bbox = (x, y, x + w, y + h)
                    norm_bbox = normalize_bbox(bbox, header_width, header_height)
                    boxes.append(norm_bbox)

            # 2. 표(원본) 영역에서 수평/수직선만 검출 (OCR X)
            cv_image = np.array(image)
            if len(cv_image.shape) == 3:
                cv_image = cv2.cvtColor(cv_image, cv2.COLOR_RGB2GRAY)
            _, binary = cv2.threshold(cv_image, 180, 255, cv2.THRESH_BINARY_INV)
            # binary = cv2.MORPH_DILATE 작성중.

            # 수평선 검출 (비율 기반 커널)
            dilate_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5,5))
            detect_horizontal = cv2.morphologyEx(binary, cv2.MORPH_DILATE, dilate_kernel, iterations=1)
            
            horizontal_kernel_size = max(1, int(image_width * horizontal_kernel_ratio))
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (horizontal_kernel_size, 1))
            detect_horizontal = cv2.morphologyEx(detect_horizontal, cv2.MORPH_OPEN, horizontal_kernel, iterations=1)
            detect_horizontal = cv2.morphologyEx(detect_horizontal, cv2.MORPH_CLOSE, horizontal_kernel, iterations=2)
            contours_h, _ = cv2.findContours(detect_horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours_h:
                x, y, w, h = cv2.boundingRect(cnt)
                bbox = (x, y, x + w, y + h)
                norm_bbox = normalize_bbox(bbox, image_width, image_height)
                words.append('─')
                boxes.append(norm_bbox)
            separate_area_util.separate_area_step_list(detect_horizontal, data_type='np_bgr', output_type='np_bgr',
                step_list=[{"name":"save","param":{"save_key":"_h_contour","tmp_save":True}}], result_map={"folder_path":process_id})

            # 수직선 검출 (비율 기반 커널)
            vertical_kernel_size = max(1, int(image_height * vertical_kernel_ratio))
            vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, vertical_kernel_size))
            detect_vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel, iterations=2)
            contours_v, _ = cv2.findContours(detect_vertical, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours_v:
                x, y, w, h = cv2.boundingRect(cnt)
                bbox = (x, y, x + w, y + h)
                norm_bbox = normalize_bbox(bbox, image_width, image_height)
                words.append('│')
                boxes.append(norm_bbox)
            separate_area_util.separate_area_step_list(detect_vertical, data_type='np_bgr', output_type='np_bgr',
                step_list=[{"name":"save","param":{"save_key":"_v_contour","tmp_save":True}}], result_map={"folder_path":process_id})
            # data에 words, boxes만 저장
            data['words'] = words
            data['boxes'] = boxes
            # data = {'words': words, 'boxes': boxes}
            ocr_save_dir = "/opt/airflow/data/class/a_class/classify/ocr"
            os.makedirs(ocr_save_dir, exist_ok=True)
            base_name = os.path.splitext(os.path.basename(item["image_path"]))[0]
            ocr_save_path = os.path.join(ocr_save_dir, f"{base_name}_ocr.json")
            json_util.save(ocr_save_path, data)

            # 워드와 박스 개수 검증 및 길이 맞추기
            if len(words) != len(boxes):
                print(f"Mismatch between words and boxes: words={len(words)}, boxes={len(boxes)}")
                min_len = min(len(words), len(boxes))
                words = words[:min_len]
                boxes = boxes[:min_len]
            if not words:
                words = ["[UNK]"]
                boxes = [[0, 0, 100, 100]]

            encoding = self.processor(
                text=words,
                boxes=boxes,
                return_tensors="pt",
                truncation=True,
                padding="max_length",
                max_length=128
            )
            return {
                **{k: v.squeeze(0) for k, v in encoding.items()},
                "labels": torch.tensor(item["label"], dtype=torch.long)
            }
    
    # 데이터셋 분할 (훈련 80%, 검증 20%)
    train_size = int(0.8 * len(dataset))
    val_size = len(dataset) - train_size
    train_dataset, val_dataset = random_split(dataset, [train_size, val_size])

    # 데이터로더 생성
    train_loader = DataLoader(
        DocDataset(train_dataset, processor),
        batch_size=2,
        shuffle=True
    )
    val_loader = DataLoader(
        DocDataset(val_dataset, processor),
        batch_size=2,
        shuffle=False
    )

    optimizer = AdamW(model.parameters(), lr=2e-5)

    for epoch in range(3):  # 3 에폭
        print(f"Epoch {epoch+1}")
        # 1. 학습
        model.train()
        train_loss = 0
        for batch in train_loader:
            try:
                inputs = {k: v.to(device) for k, v in batch.items() if k != "labels"}
                outputs = model(**inputs, labels=batch["labels"].to(device))
                loss = outputs.loss
                loss.backward()
                optimizer.step()
                optimizer.zero_grad()
                train_loss += loss.item()
            except Exception as e:
                print(f"Batch 실패: {str(e)}")
                continue
        print(f"Epoch {epoch+1} 훈련 손실: {train_loss/len(train_loader):.4f}")

        # 2. 검증
        model.eval()
        
        val_total = len(val_dataset)
        val_loss = 0
        correct = 0
        with torch.no_grad():
            for batch in val_loader:
                inputs = {k: v.to(device) for k, v in batch.items() if k != "labels"}
                outputs = model(**inputs, labels=batch["labels"].to(device))
                val_loss += outputs.loss.item()
                preds = torch.argmax(outputs.logits, dim=1)
                correct += (preds == batch["labels"].to(device)).sum().item()

        print(f"Epoch {epoch+1} 검증 손실: {val_loss/len(val_loader):.4f}, 정확도: {correct/val_total:.2%}")

    try:
        model.save_pretrained(model_dir)
    except (OSError, FileNotFoundError):  # 디렉토리가 없어서 난 오류는 폴더 생성 후 재실행
        os.makedirs(model_dir, exist_ok=True)
        model.save_pretrained(model_dir)

    print(f"모델 저장 완료: {model_dir}")

    return model_dir

def train_ml(dataset: list, model_dir: str, target_model_name: str = None, class_key: str = ""):
    """
    TargetEncoder를 포함한 sklearn 파이프라인을 사용하여 여러 모델을 학습하고 저장합니다.
    - dataset 리스트를 pandas DataFrame으로 변환
    - 전처리기(ColumnTransformer)와 다양한 모델을 포함하는 파이프라인 구축
    - 각 모델을 학습하고, pickle 파일로 저장
    """
    import os
    import pandas as pd
    import numpy as np
    import pickle
    from sklearn.model_selection import train_test_split
    from sklearn.compose import ColumnTransformer
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler, OneHotEncoder
    from category_encoders import TargetEncoder
    
    # 여러 모델 import
    from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier, GradientBoostingClassifier
    from sklearn.svm import SVC
    from sklearn.linear_model import LogisticRegression
    from xgboost import XGBClassifier
    from lightgbm import LGBMClassifier
    from sklearn.tree import DecisionTreeClassifier
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.naive_bayes import GaussianNB
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    print("1. 데이터셋 전처리 및 특징 추출 시작...")
    processed_data = []
    for item in dataset:
        try:
            features = extract_feature_for_table_doc_util.preprocess_image_and_extract_features(item['image_path'], class_key=class_key)
            features['y'] = item['label']
            processed_data.append(features)
        except Exception as e:
            print(f"이미지 전처리 실패: {item['image_path']} - {e}")
            continue

    if not processed_data:
        print("전처리된 데이터가 없습니다. 학습을 중단합니다.")
        return
        
    df = pd.DataFrame(processed_data)
    print(df)
    # 결측치 처리
    df.fillna(value=np.nan, inplace=True) # TargetEncoder는 NaN 값을 처리할 수 있으므로, NaN으로 유지

    # 특성 그룹 정의 (모든 피처 그룹을 사용할 수 있지만, 해당 피처만 사용해도 어느정도 성능은 보장됨.)
    numerical_features = ['text_span_x_min', 'text_span_y_min', 'horiz_span_x_min']
    onehot_encoding_features = ['return_tensors', 'padding']
    target_encoding_features = ['cleaned_processed_text']
    
    # 전처리기 및 파이프라인 정의
    numerical_transformer = SimpleImputer(strategy='mean', add_indicator=True)
    onehot_transformer = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='most_frequent')),
        ('onehot', OneHotEncoder(handle_unknown='ignore'))
    ])
    target_transformer = TargetEncoder(
        cols=target_encoding_features,
        min_samples_leaf=20,
        smoothing=10
    )
    preprocessor = ColumnTransformer(
        transformers=[
            ('numerical', numerical_transformer, numerical_features),
            ('onehot', onehot_transformer, onehot_encoding_features),
            ('target', target_transformer, target_encoding_features)
        ],
        remainder='passthrough'
    )
    final_sklearn_pipeline = None

    X = df.drop('y', axis=1)
    y = df['y']

    # 데이터셋 분리
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=123)

    print("2. 여러 모델 학습 및 저장 시작...")
    
    os.makedirs(model_dir, exist_ok=True)
    
    # 학습할 여러 머신러닝 모델 정의
    models = [
        ('ExtraTreesClassifier', ExtraTreesClassifier(n_jobs=-1, random_state=123)),
        ('RandomForestClassifier', RandomForestClassifier(n_jobs=-1, random_state=123)),
        ('GradientBoostingClassifier', GradientBoostingClassifier(random_state=123)),
        ('XGBClassifier', XGBClassifier(n_jobs=-1, random_state=123, use_label_encoder=False, eval_metric='logloss')),
        ('LGBMClassifier', LGBMClassifier(n_jobs=-1, random_state=123)),
        ('SVC', SVC(random_state=123, probability=True)),
        ('LogisticRegression', LogisticRegression(n_jobs=-1, random_state=123)),
        ('DecisionTreeClassifier', DecisionTreeClassifier(random_state=123)),
        ('KNeighborsClassifier', KNeighborsClassifier(n_jobs=-1)),
        ('GaussianNB', GaussianNB()),
        ('LinearDiscriminantAnalysis', LinearDiscriminantAnalysis())
    ]

    for model_name, model in models:
        if target_model_name and model_name != target_model_name:
            print(f"Skipping model: {model_name} (not in target_model_name)")
            continue
        print(f"\n--- {model_name} 학습 시작 ---")
        try:
            # 새로운 파이프라인 생성 (매 반복마다 새로운 모델로 교체)
            final_sklearn_pipeline = Pipeline(steps=[
                ('preprocessor', preprocessor),
                ('final_imputer', SimpleImputer(strategy='mean')),
                ('classifier', model)
            ])
            
            # 파이프라인을 한 번에 학습 (y_train을 사용하여 전처리와 학습 동시 진행)
            final_sklearn_pipeline.fit(X_train, y_train)

            train_accuracy = final_sklearn_pipeline.score(X_train, y_train)
            test_accuracy = final_sklearn_pipeline.score(X_test, y_test)
            print(f"학습 데이터 정확도: {train_accuracy:.4f}")
            print(f"테스트 데이터 정확도: {test_accuracy:.4f}")

            model_path = os.path.join(model_dir, f"sklearn_pipeline_{model_name}.pkl")
            with open(model_path, 'wb') as f:
                pickle.dump(final_sklearn_pipeline, f)
            print(f"파이프라인이 '{model_path}' 파일로 저장되었습니다.")
        except Exception as e:
            print(f"모델 학습 실패: {model_name} - {str(e)}")
            continue
            
    print("\n모든 모델 학습 및 저장이 완료되었습니다.")
    return model_dir

#데이터가 충분하지 않을 때 증강을 통해 데이터셋을 확장합니다.
@task(pool='ocr_pool') 
def image_data_augment(origin_dir: str, ready_dir: str, threshold=200, aug_limit=3):
    from torchvision import transforms
    from PIL import Image
    from torchvision.transforms import functional as F
    
    image_paths = file_util.get_image_paths(origin_dir)
    os.makedirs(ready_dir, exist_ok=True)
    
    if len(image_paths) < threshold:
        num_aug = min(int(threshold / len(image_paths)), aug_limit)
    else:
        num_aug = 1 # 원본만
    def get_augmentation(width, height):
        return transforms.Compose([
            transforms.Resize((height*2, width*2), interpolation=InterpolationMode.BICUBIC),
            transforms.RandomAffine(degrees=5, translate=(0.02, 0.02), fill=255, interpolation=InterpolationMode.BICUBIC),
            transforms.Resize((height, width), interpolation=InterpolationMode.BICUBIC),
            transforms.ColorJitter(brightness=0.2, contrast=0.2)
        ])
    
    for img_path in image_paths:
        img = Image.open(img_path).convert('RGB')
        width, height = img.size
        augmentation = get_augmentation(width, height) if num_aug > 1 else None

        base_name = os.path.splitext(os.path.basename(img_path))[0]
        orig_save_path = os.path.join(ready_dir, f"{base_name}_aug0.png")
        img.save(orig_save_path)
        if augmentation:
            for i in range(1,num_aug):
                aug_img = augmentation(img) # 증강 함수
                save_path = os.path.join(ready_dir, f"{base_name}_aug{i}.png")
                aug_img.save(save_path)
                print(f"증강 이미지 저장: {save_path}")
