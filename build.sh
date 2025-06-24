#!/bin/bash

# Airflow 도커 컴포즈 디렉토리로 이동 (경로를 실제 위치로 수정)
cd /home/digital-033/work/docker/digitalflow

# 전체 중지 후 다시 시작
docker compose build
docker compose up -d
