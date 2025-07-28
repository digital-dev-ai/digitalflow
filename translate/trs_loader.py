# korean_labels.py

trs_label = {
    "providers_fab_auth_manager_security_manager_override": {
        "User_label": "사용자 목록",
        "Role_label": "권한 그룹 관리",
        "User_stat_label": "사용자 통계",
        "User_register_label": "사용자 등록",
        "Actions_label": "활동",
        "resource_label": "리소스",
        "permission_label": "권한 목록",
        "category": "사용자 및 권한 관리",
    },
    "www_extensions_init_appbuilder_links": {
        "DAGs_label": "배치관리",
        "Cluster Activity_label": "로그 분석",
        "Datasets_label": "데이터셋"
    },
    "www_extensions_init_views": {
        "browse_category": "탐색",
        "admin_category": "시스템 관리",
        "dag_run_label": "배치 실행",
        "job_label": "작업",
        "task_instance_label": "작업 인스턴스",
        "task_reschedule_label": "작업 재조정",
        "trigger_label": "트리거",
        "audit_log_label": "감사 로그",
        "variable_label": "매개 변수",
        "config_label": "구성",
        "connection_label": "연결 관리",
        "pool_label": "풀",
        "provider_label": "제공자",
        "sla_miss_label": "서비스 계약 수준 미달",
        "plugin_label": "플러그인",
        "xcom_label": "크로스 커뮤니케이션",
        "dag_dependency_label": "배치 종속성"
    },
    "www_static_css_main": {},
    "www_static_dist_dags": {
        "search_dropdown": "태그로 배치를 필터링합니다.",
    },
    "www_static_dist_main": {},
    "www_static_dist_js_dags": {
        "search_dropdown": "태그로 배치를 필터링합니다.",
    },
    "www_templates_airflow_dag": {},
    "www_templates_airflow_dags": {
        "sort_col_title": "{{ attribute_name }}를 {{ new_ordering_direction }}로 정렬.",
        "page_title": "배치관리",
        "status_all_title": "활성화 가능하거나 일시정지된 배치를 보여줍니다.",
        "status_all_label": "전체",
        "status_active_title": "활성화된 배치를 보여줍니다.",
        "status_active_label": "활성화",
        "status_paused_title": "일시정지된 배치를 보여줍니다.",
        "status_paused_label": "일시정지",
        "running_dag_runs_title": "실행 중인 배치를 보여줍니다.",
        "running_dag_runs_label": "실행중",
        "failed_dag_runs_title": "최근 실행 시 실패한 배치를 보여줍니다.",
        "failed_dag_runs_label": "실행 실패",
        "dag_search": "배치명 검색",
        "auto_refresh": "자동-새로 고침",
        "pause_unpause_pop": "하단의 토글버튼을 사용하여 배치를 일시 정지/실행합니다. 스케줄러는 일시 중지된 배치에 대해 새 작업 인스턴스를 예약하지 않습니다. 일시 중지 시, 이미 실행 중인 작업은 영향을 받지 않습니다.",
        "DAG": "배치명",
        "owners": "소유자",
        "run_status": "실행 현황",
        "run_status_detail":"배치 실행 시  상태를 집계하여 보여줍니다.",
        "schedule": "스케줄",
        "last_run": "실행 시간",
        "last_run_detail": "최근 배치 실행 날짜, 시간을 보여줍니다.",
        "next_run": "다음 실행",
        "next_run_detail": "다음 배치 실행의 논리적 날짜/시간, 또는 데이터셋으로 실행하는 배치의 경우에 마지막 배치 실행 이후 업데이트된 데이터셋 수를 보여줍니다",
        "last_task": "최근 작업",
        "last_task_detail": "모든 활성화된 배치 실행 또는 현재 활성화되지 않은 경우 가장 최근 실행의 작업 상태를 보여줍니다.",
        "actions": "동작",
        "link": "링크",
        "pause_unpause": "배치 정지/실행",
        "time_table_title": "스케줄",
        "summary": "전체 <strong>{{ num_dag_from }}-{{ num_dag_to }}</strong> 중 <strong>{{ num_of_all_dags }}</strong>개의 배치",
        'btn_dag': "배치 실행",
        "btn_renew": "배치 갱신",
        "btn_del": "배치 삭제",
    },
    "www_templates_airflow_main": {
        "version": "버전",
        "Git_version": "Git 버전"
    },
    "www_templates_apddbuilder_navbar_right": {
        "UTC": "협정 세계시",
        "local": "현지 시간",
        "other": "그 외 시간",
        "profile": "프로필",
        "log-out": "로그아웃",
        "log-in": "로그인"
    },
    "www_templates_apddbuilder_navbar": {
        "png_insert": "<img class=\"brand-logo\" viewBox=\"0 0 180 60\" src=\"/static/dship.png\" alt=\"Company Logo\">"
    },
}

# { trs_dict.www_templates_airflow_dags. }}