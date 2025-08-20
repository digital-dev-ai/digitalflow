from __future__ import annotations
import pendulum
from airflow.datasets import Dataset
from airflow.models.dag import DAG
from airflow.operators.bash import BashOperator

# 데이터셋을 정의합니다
my_dataset = Dataset("s3://dataset-bucket/example.csv")

with DAG(
    dag_id="dataset_consumer_dag",
    start_date=pendulum.datetime(2023, 1, 1, tz="UTC"),
    schedule=[my_dataset],  # 이 DAG는 데이터셋에 의해 트리거됩니다
    catchup=False,
    tags=["dataset_example"],
):
    # 이 태스크는 데이터셋이 업데이트된 후에 실행됩니다
    BashOperator(
        task_id="process_dataset_task",
        bash_command="echo '업데이트된 데이터셋을 처리합니다...'",
    )