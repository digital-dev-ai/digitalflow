@echo off
::Airflow 도커 컴포즈 디렉토리로 이동 (필요시 경로 수정)
cd /d D:\docker\digitalflow

::전체 중지 후 다시 시작
docker compose down --rmi all --volumes --remove-orphans
docker compose build
docker compose up -d