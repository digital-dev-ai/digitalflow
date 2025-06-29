from airflow.decorators import task
from collections import Counter
from pathlib import Path
from PIL import Image
import numpy as np
import cv2, os
from typing import Any,List
import uuid
from utils.db.maria_util import insert_map
from utils import file_util, json_util
from utils import type_convert_util
from airflow.models import Variable,XCom
from datetime import datetime
import pytesseract
from scipy.ndimage import interpolation as inter
from transformers import AutoModelForSequenceClassification, AutoProcessor
import torch
import torch.nn.functional as F  # 상단에 추가

RESULT_FOLDER = Variable.get("RESULT_FOLDER", default_var="/opt/airflow/data/result")
TEMP_FOLDER = Variable.get("TEMP_FOLDER", default_var="/opt/airflow/data/temp")
NONE_DOC_IMAGE_DIR = Variable.get("NONE_CLASS_FOLDER", default_var="/opt/airflow/data/none_class") # 비서식 일반 문서 이미지

from utils import file_util
import random
import shutil
@task
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

@task
def build_balanced_dataset(root_path):
    """균형이 맞춰진 데이터셋 구성"""
    true_folder = f"{root_path}/true"
    false_folder = f"{root_path}/false"
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


@task
def train_lilt(dataset: list, model_dir:str):
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

            def normalize_bbox(bbox, image_width, image_height):
                x1, y1, x2, y2 = bbox
                x1 = int(1000 * (x1 / image_width))
                y1 = int(1000 * (y1 / image_height))
                x2 = int(1000 * (x2 / image_width))
                y2 = int(1000 * (y2 / image_height))
                return [x1, y1, x2, y2]

            try:
                data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, lang='kor+eng', config='--psm 4 --oem 3')
            except Exception as e:
                print(f"OCR error: {e}")
                data = {"text": [], "left": [], "top": [], "width": [], "height": []}
            words = []
            boxes = []
            for word, x, y, w, h in zip(data['text'], data['left'], data['top'], data['width'], data['height']):
                if word.strip():  # 공백이나 빈 문자열이 아니면
                    words.append(word.strip())
                    # 바운딩 박스 좌표 정규화 (x, y, x+w, y+h)
                    bbox = (x, y, x + w, y + h)
                    norm_bbox = normalize_bbox(bbox, image_width, image_height)
                    boxes.append(norm_bbox)

            
            # 워드와 박스 개수 검증 및 길이 맞추기
            if len(words) != len(boxes):
                print(f"Mismatch between words and boxes: words={len(words)}, boxes={len(boxes)}")
                min_len = min(len(words), len(boxes))
                words = words[:min_len]
                boxes = boxes[:min_len]
            
            # 단어가 하나도 없으면 "[UNK]" 하나로 처리
            if not words:
                words = ["[UNK]"]
                boxes = [[0, 0, 100, 100]]
            
            # boxes를 2D 리스트로 변환 (LayoutLMv3 요구사항)
            #box_list = [list(box) for box in boxes] if boxes else [[0, 0, 100, 100]]

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

@task
def image_data_augment(origin_dir: str, ready_dir: str, threshold=200):
    from torchvision import transforms
    from PIL import Image
    from torchvision.transforms import functional as F
    
    def get_augmentation():
        return transforms.Compose([
            transforms.RandomAffine(degrees=5, translate=(0.02, 0.02), fill=255),
            transforms.ColorJitter(brightness=0.2, contrast=0.2),
            transforms.ToTensor()
        ])

    image_paths = file_util.get_image_paths(origin_dir)
    if len(image_paths) < threshold:
        augmentation = get_augmentation() # 증강 함수
        num_aug = 3  # 원본 1장당 증강 이미지 개수
    else:
        augmentation = transforms.ToTensor() # 증강없이 진행
        num_aug = 1 # 원본만
    os.makedirs(ready_dir, exist_ok=True)

    for img_path in image_paths:
        img = Image.open(img_path).convert('RGB')
        base_name = os.path.splitext(os.path.basename(img_path))[0]
        for i in range(num_aug):
            aug_img = augmentation(img)
            aug_img_pil = transforms.ToPILImage()(aug_img)
            save_path = os.path.join(ready_dir, f"{base_name}_aug{i}.png")
            aug_img_pil.save(save_path)

