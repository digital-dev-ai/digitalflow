from typing import Any
from utils.db.maria_util import execute, execute_many


def insert_map(key, params:Any=None, fetch=False):
    map = {
        "insertRun":"INSERT INTO TB_AF_RUN(dag_id, run_id, start_date, status) VALUES (%s, %s, current_timestamp(), 'P')",
        "insertTargetFile":"INSERT INTO TB_AF_TARGET(run_id, target_id, content) VALUES (%s, %s, %s)",
        "insertClassifyResult":"INSERT INTO TB_AF_TARGET(run_id, target_id, content) VALUES (%s, %s, %s)"
    }
    if isinstance(params, list):  # 벌크 삽입
        print("many",len(params))
        execute_many(map[key], params_list=params)
    else:  # 단일 삽입 (기존 방식 유지)
        print("one", len(params))
        execute(map[key], params=params, fetch=fetch)
    

def update_map(key, params:dict=None, fetch=False):
    map = {
        "updateRunEnd":"UPDATE TB_AF_RUN SET end_date = current_timestamp(), status = %s WHERE dag_id = %s and run_id = %s",
        "updateTargetContent":"UPDATE TB_AF_TARGET SET content = %s, updt=current_timestamp()+5000000 WHERE run_id = %s and target_id = %s",
        "updateTargetContentDetail":"UPDATE TB_AF_TARGET SET content = JSON_SET(content, %s, %s) WHERE run_id = %s and target_id = %s",
    }
    print(" query : ",map[key],params)
    execute(map[key], params=params, fetch=fetch)
