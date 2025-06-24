#!/bin/bash

# variables.json 파일이 있으면 import
if [ -f "/variables.json" ]; then
  airflow variables import /variables.json
fi

# 기존 Airflow entrypoint 실행 (신호 전달을 위해 exec 사용)
exec /entrypoint "$@"
