#!/bin/bash

# Airflow 도커 컴포즈 디렉토리로 이동 (경로를 실제 위치로 수정)
cd /home/digital-033/work/docker/digitalflow

# 모든 Airflow 컨테이너 재시작
docker compose restart
