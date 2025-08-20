from __future__ import annotations
import pendulum
from airflow.datasets import Dataset
from airflow.models.dag import DAG
from airflow.operators.bash import BashOperator

# 데이터셋을 정의합니다
my_dataset = Dataset("s3://dataset-bucket/example.csv")

with DAG(
    dag_id="dataset_producer_dag",
    start_date=pendulum.datetime(2023, 1, 1, tz="UTC"),
    schedule=None,  # 이 DAG는 시간 기준으로 스케줄링되지 않습니다
    catchup=False,
    tags=["dataset_example"],
):
    # 이 태스크는 데이터셋을 "생성"하거나 업데이트합니다
    BashOperator(
        task_id="update_dataset_task",
        bash_command="echo 'example.csv 데이터셋을 업데이트합니다...'",
        outlets=[my_dataset],  # 'outlets' 파라미터로 데이터셋과 태스크를 연결합니다
    )