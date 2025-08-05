from logging import exception
from typing import Any, Union
from utils.db.maria_util import execute, execute_many

#insert만 벌크 실행 가능
def insert_map(key, params:Union[list,tuple]=None, fetch:bool=False, return_id:bool=False):
    map = {
        "insertRun":"INSERT INTO TB_AF_RUN(dag_id, run_id, start_date, status) VALUES (%s, %s, current_timestamp(), 'P')", # W 대기, P 진행중
        "insertTargetFile":"INSERT INTO TB_AF_TARGET(run_id, target_id, content) VALUES (%s, %s, %s)",
        "insertClassifyResult":"INSERT INTO TB_AF_TARGET(run_id, target_id, content) VALUES (%s, %s, %s)",
        "insertTranslateLog":"INSERT INTO TB_OCR_TRN_LOG (TRN_TABLE_NAME, TRN_TABLE_PK, TRN_COL_ID, ORI_TEXT, TRN_TEXT) VALUES (%s, %s, %s, %s, %s)"
    }
    if isinstance(params, list):  # 벌크 삽입(벌크 입력은 return_id 지원 안함)
        print("bulk insert execute",params)
        return execute_many(map[key], params_list=params) 
    elif isinstance(params, tuple):  # 단일 삽입
        print("insert execute",params)
        return execute(map[key], params=params, fetch=fetch, return_id=return_id)
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
    placeholders = ''
    if key=="selectDocClassId":
        placeholders = ','.join(['%s'] * len(params)) 
    map = {
        "selectDocClassId": f"SELECT DOC_CLASS_ID FROM VW_DI_DOC_LAYOUT_SECTION "+
                "WHERE LAYOUT_CLASS_ID IN ({placeholders}) "+
                "GROUP BY DOC_CLASS_ID ORDER BY COUNT(*) DESC "
                "FETCH FIRST 1 ROW ONLY ",
        "selectPatternInfo":"SELECT A.FORMAT_INFO "+
                "FROM TB_DS_COLUMN A INNER JOIN TB_DI_BLOCK_CLASS B ON A.COLUMN_ID=B.COLUMN_ID "+
                "WHERE B.SECTION_CLASS_ID = %s AND BLOCK_ROW_NUM= %s AND BLOCK_COL_NUM = %s "+
                "ORDER BY B.BLOCK_CLASS_ID DESC LIMIT 1 ",
        "selectBlockCrctnMatched":"SELECT A.CRRCT_TEXT  "+
                "FROM TB_DI_BLOCK_CRCTN A INNER JOIN TB_DI_BLOCK_CLASS B ON A.BLOCK_CLASS_ID=B.BLOCK_CLASS_ID "+
                "WHERE B.SECTION_CLASS_ID=%s AND B.BLOCK_ROW_NUM=%s AND B.BLOCK_COL_NUM=%s AND A.ERROR_TEXT=%s " +
                "ORDER BY CRCTN_ORDER DESC LIMIT 1 ",
    }
    print(" query : ",map[key], params)
    result = execute(map[key], params=params, fetch=True)
    if result:
        print("result : ",result[0][0])
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


#에외처리용
def select_doc_class_id(params:list) -> int:
    if not params and len(params) == 0:
        return None
    placeholders = ','.join(['%s'] * len(params)) 
    query = f"""
        SELECT DOC_CLASS_ID FROM VW_DI_DOC_LAYOUT_SECTION 
         WHERE LAYOUT_CLASS_ID IN ({placeholders}) 
         GROUP BY DOC_CLASS_ID ORDER BY COUNT(*) DESC 
         FETCH FIRST 1 ROW ONLY 
    """
    print(" query : ",query, params)
    result = execute(query, params=params, fetch=True)
    if result:
        return result[0][0]  # 값 1개만 반환
    else:
        return None 


def insert_structed_ocr_result(doc_class_id:tuple=None, structed_doc:dict=None):
    select_query = """
        SELECT B.TABLE_NAME, A.COLUMN_NAME AS PK, C.TABLE_NAME AS PARENT_TABLE_NAME, D.COLUMN_NAME AS PARENT_PK 
            FROM TB_DS_COLUMN A 
            INNER JOIN TB_DS_TABLE B ON A.TABLE_ID=B.TABLE_ID 
            LEFT OUTER JOIN (TB_DS_TABLE C INNER JOIN TB_DS_COLUMN D ON C.TABLE_ID=D.TABLE_ID AND D.IS_PK='Y') 
            ON B.PARENT_TABLE_ID=C.TABLE_ID 
            WHERE B.TABLE_ID IN ( 
                SELECT DISTINCT Z.TABLE_ID FROM VW_DI_DOC_LAYOUT_SECTION X 
                INNER JOIN TB_DI_BLOCK_CLASS Y ON X.SECTION_CLASS_ID=Y.SECTION_CLASS_ID 
                INNER JOIN TB_DS_COLUMN Z ON Z.COLUMN_ID=Y.COLUMN_ID 
                WHERE X.DOC_CLASS_ID= %s 
                ) 
            AND A.IS_PK='Y' """
    dict_key_list = ['table_name','pk','parent_table_name','parent_pk']
    
    print(" query : ",select_query,doc_class_id)
    result = execute(select_query, params=doc_class_id, fetch=True)
    print("result : ",result)
    table_list = tuples_to_dicts(result,dict_key_list)
    # 부모가 없는 테이블 먼저 작업
    pk_map = {}
    for table_info in table_list:
        if table_info["parent_table_name"] is None:
            # TB_OCR_BILD_BASIC_INFO에 먼저 데이터 삽입 및 BILD_SEQ_NUM 얻기
            table_name = table_info["table_name"]
            pk_name = table_info["pk"]

            records = structed_doc.get(table_name, [])
            if not records:
                print(f"경고: {table_name} 테이블에 삽입할 데이터가 없습니다.")
                continue
            elif len(records)>1:
                print(f"경고: 대표 테이블인 {table_name}에는 1건씩만 입력 가능합니다.")
                return "error"
            
            # pk를 제외한 컬럼 목록 준비
            col_list = list(records[0].keys())
            if pk_name in col_list: # PK는 항상 autoincrease
                col_list.remove(pk_name)

            col_placeholders = ', '.join(['%s'] * len(col_list))
            col_names_quoted = ', '.join([f"`{col}`" for col in col_list])
            insert_sql = f"INSERT INTO `{table_name}` ({col_names_quoted}) VALUES ({col_placeholders})"
            print(insert_sql)
            for record in records:
                col_values = [record.get(col, None) for col in col_list]
                pk_value = execute(insert_sql, params=col_values, return_id=True)
                pk_map.setdefault(table_name, {}).setdefault(pk_name, []).append(pk_value)
            print(f"{table_name}에 데이터 삽입 완료. pk:{pk_value}")
    
    # 부모가 있고 pk_map에 pk가 있는 테이블 작업
    for table_info in table_list:
        if table_info["parent_table_name"]:
            # TB_OCR_BILD_BASIC_INFO에 먼저 데이터 삽입 및 BILD_SEQ_NUM 얻기
            table_name = table_info["table_name"]
            pk_name = table_info["pk"]
            parent_table_name = table_info["parent_table_name"]
            parent_pk_name = table_info["parent_pk"]

            records = structed_doc.get(table_name, [])
            if not records:
                print(f"경고: {table_name} 테이블에 삽입할 데이터가 없습니다.")
                continue
            # pk, 부모pk를 제외한 컬럼 목록 준비
            col_list = list(records[0].keys())
            if pk_name in col_list: # PK는 항상 autoincrease
                col_list.remove(pk_name)
            if parent_pk_name in col_list: # 부모PK는 별도 입력
                col_list.remove(parent_pk_name)
            if not col_list:
                print(f"경고: {table_name} 테이블에 삽입할 데이터가 없습니다.")
                continue

            col_placeholders = ', '.join(['%s'] * len(col_list))
            col_names_quoted = ', '.join([f"`{col}`" for col in col_list])
            parent_pk_placeholder = ', %s'
            parent_pk_name_quoted = f', {parent_pk_name}'
            insert_sql = f"INSERT INTO `{table_name}` ({col_names_quoted}{parent_pk_name_quoted}) VALUES ({col_placeholders}{parent_pk_placeholder})"
            for record in records:
                col_values = [record.get(col, None) for col in col_list]
                parent_pk_value = pk_map.get(parent_table_name,{}).get(parent_pk_name,"")[0]
                col_values.append(parent_pk_value)
                pk_value = execute(insert_sql, params=col_values, return_id=True)
                print(f"{table_name}에 데이터 삽입 완료. pk:{pk_value}")

def select_translate_target_list(table_name: str, id_col_name: str):
    """
    번역 대상 테이블과 컬럼을 선택합니다.
    :return: 번역 대상 테이블과 컬럼의 리스트
    """
    col_values = (table_name,)
    query = f"""SELECT B.*
    FROM {table_name} B
    LEFT JOIN TB_OCR_TRN_LOG A 
    ON B.{id_col_name} = A.TRN_TABLE_PK 
    AND A.TRN_TABLE_NAME = %s
    WHERE A.TRN_TABLE_PK IS NULL;
    """
    print(" query : ",query, col_values)
    list = execute(query, params=col_values, fetch=True, dictionary=True)
    return list 
    
def update_for_translate(table_name: str, id_col_name:str, latest_id: str, update_target: dict):
    """
    번역된 컬럼을 원본 테이블에 업데이트합니다.
    
    :param updates: dict - 컬럼명과 번역된 텍스트의 딕셔너리
    """        
    # 원본 테이블 업데이트
    set_clauses = [f"{col} = %s" for col in update_target.keys()]
    set_values = [v[1] for v in update_target.values()]
    
    update_query = f"UPDATE {table_name} SET {', '.join(set_clauses)} WHERE {id_col_name} = %s;"
    update_values = set_values + [latest_id]
    execute(update_query, params=update_values)

    insert_log_query = "INSERT INTO TB_OCR_TRN_LOG (TRN_TABLE_NAME, TRN_TABLE_PK, TRN_COL_ID, ORI_TEXT, TRN_TEXT) VALUES (%s, %s, %s, %s, %s)"
    params_list = [
        (table_name, latest_id, col, ori_text, trn_text)
        for col, (ori_text, trn_text) in update_target.items()
    ]
    execute_many(insert_log_query, params_list=params_list)

    return