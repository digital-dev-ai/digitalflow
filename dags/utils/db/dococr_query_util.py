from typing import Any, Union
from utils.db.maria_util import execute, execute_many

#insert만 벌크 실행 가능

def insert_map(key, params:Union[list,tuple]=None, fetch:bool=False):
    map = {
        "insertRun":"INSERT INTO TB_AF_RUN(dag_id, run_id, start_date, status) VALUES (%s, %s, current_timestamp(), 'P')",
        "insertTargetFile":"INSERT INTO TB_AF_TARGET(run_id, target_id, content) VALUES (%s, %s, %s)",
        "insertClassifyResult":"INSERT INTO TB_AF_TARGET(run_id, target_id, content) VALUES (%s, %s, %s)"
    }
    if isinstance(params, list):  # 벌크 삽입
        print("bulk insert execute",len(params))
        execute_many(map[key], params_list=params)
    elif isinstance(params, tuple):  # 단일 삽입 (기존 방식 유지)
        execute(map[key], params=params, fetch=fetch)
    else :
        print("error", "파라미터가 list나 tuple이 아닙니다.")
        raise ValueError("파라미터가 list나 tuple이 아닙니다.")
    

def update_map(key, params:tuple=None):
    map = {
        "updateRunEnd":"UPDATE TB_AF_RUN SET end_date = current_timestamp(), status = %s WHERE dag_id = %s and run_id = %s ",
        "updateTargetContent":"UPDATE TB_AF_TARGET SET content = %s WHERE run_id = %s and target_id = %s ",
        "updateTargetContentDetail":"UPDATE TB_AF_TARGET SET content = JSON_SET(content, %s, %s) WHERE run_id = %s and target_id = %s ",
    }
    print(" query : ",map[key],params)
    execute(map[key], params=params, fetch=False)
    

def select_list_map(key, params:tuple=None):
    map = {
        "selectLayoutList": ("SELECT A.LAYOUT_CLASS_ID, A.LAYOUT_NAME, A.DOC_CLASS_ID, A.IMG_PREPROCESS_INFO, A.CLASSIFY_AI_INFO "+
                "FROM TB_DI_LAYOUT_CLASS AS A "+
                "ORDER BY A.LAYOUT_ORDER, A.LAYOUT_CLASS_ID "
            ,['layout_class_id','layout_name','doc_class_id','img_preprocess_info','classify_ai_info']
        ),
        "selectSectionList": ("SELECT A.SECTION_CLASS_ID, A.SECTION_NAME, A.SECTION_TYPE, A.SEPARATE_AREA_INFO, A.SEPARATE_BLOCK_INFO, A.OCR_INFO, A.CLEANSING_INFO, A.STRUCTURING_INFO "+
                "FROM TB_DI_SECTION_CLASS AS A "+
                "WHERE A.LAYOUT_CLASS_ID = %s "+
                "ORDER BY A.SECTION_ORDER, A.SECTION_CLASS_ID "
            ,['section_class_id','section_name','section_type','separate_area','separate_block','ocr','cleansing','structuring']
        ),
        "selectBlockList": ("SELECT A.BLOCK_ROW_NUM, A.BLOCK_COL_NUM, A.BLOCK_TYPE, A.DEFAULT_TEXT, C.TABLE_NAME, B.COLUMN_NAME "+
                "FROM TB_DI_BLOCK_CLASS A LEFT OUTER JOIN TB_DS_COLUMN B ON A.COLUMN_ID =B.COLUMN_ID "
                "LEFT OUTER JOIN TB_DS_TABLE C ON B.TABLE_ID=C.TABLE_ID "+
                "WHERE A.SECTION_CLASS_ID = %s "+
                "ORDER BY A.BLOCK_ROW_NUM, A.BLOCK_COL_NUM "
            ,['block_row_num','block_col_num','block_type','default_text','table_name','column_name']
        ),
        "selectBlockCrctnList": ("SELECT A.ERROR_TEXT, A.CRRCT_TEXT  "+
                "FROM TB_DI_BLOCK_CRCTN A INNER JOIN TB_DI_BLOCK_CLASS B ON A.BLOCK_CLASS_ID=B.BLOCK_CLASS_ID "+
                "WHERE B.SECTION_CLASS_ID=%s AND B.BLOCK_ROW_NUM=%s AND B.BLOCK_COL_NUM=%s "
                "ORDER BY CRCTN_ORDER DESC "
            ,['error_text','crrct_text']
        ),
    }
    print(" query : ",map[key][0],params)
    result = execute(map[key][0], params=params, fetch=True)
    print("result : ",result)
    return tuples_to_dicts(result,map[key][1])

def select_one_map(key, params:tuple=None):
    map = {
        "selectClassId": "SELECT A.DOC_CLASS_ID "+
                "FROM TB_DI_DOC_CLASS A "+
                "WHERE A.DOC_NAME = %s "+
                "ORDER BY A.DOC_CLASS_ID DESC LIMIT 1 ",
        "selectPatternInfo":"SELECT A.FORMAT_INFO "+
                "FROM TB_DS_COLUMN A INNER JOIN TB_DI_BLOCK_CLASS B ON A.COLUMN_ID=B.COLUMN_ID "+
                "WHERE B.SECTION_CLASS_ID = %s AND BLOCK_ROW_NUM= %s AND BLOCK_COL_NUM = %s "+
                "ORDER BY B.BLOCK_CLASS_ID DESC LIMIT 1 ",
    }
    print(" query : ",map[key], params)
    result = execute(map[key], params=params, fetch=True)
    if result:
        return result[0][0]  # 값 1개만 반환
    else:
        return None 

def tuples_to_dicts(rows, columns):
    """
    튜플 기반 결과를 딕셔너리 리스트로 변환합니다.
    
    :param rows: list of tuple - DB 결과 행들
    :param columns: list of str - 컬럼명 리스트
    :return: list of dict - 컬럼명을 키로 하는 딕셔너리 리스트
    """
    result = []
    for row in rows:
        if len(row) != len(columns):
            raise ValueError(f"컬럼 수 불일치: row의 컬럼 수 {len(row)}와 columns의 수 {len(columns)}가 다릅니다.")
        result.append(dict(zip(columns, row)))
    return result
