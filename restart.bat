@echo off
::Airflow 도커 컴포즈 디렉토리로 이동 (필요시 경로 수정)
cd /d D:\docker\digitalflow

::모든 Airflow 컨테이너 재시작
docker compose restart