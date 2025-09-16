from typing import Any, Union
from dags.utils.db.maria_util import execute, execute_many
from logging import exception


# insert만 벌크 실행 가능
def insert_map(key, params: Union[list, tuple] = None, fetch: bool = False, return_id: bool = False):
    map = {
        "insertDocClass": "INSERT INTO TB_DI_DOC_CLASS(DOC_NM) VALUES (%s)",
        "insertLayoutClass": "INSERT INTO TB_DI_LAYOUT_CLASS(DOC_CLASS_ID, LAYOUT_NM, LAYOUT_DESC, LAYOUT_ORDR, IMG_PREPROCESS_INFO, CLASSIFY_AI_INFO) VALUES (%s, %s, %s, %s, %s, %s)",
        "insertSectionClass": "INSERT INTO TB_DI_SECTION_CLASS(LAYOUT_CLASS_ID, SECTION_NM, SECTION_DESC, SECTION_TYPE, SECTION_ORDR, SEPARATE_SECTION_INFO, SEPARATE_BLOCK_INFO, OCR_INFO, CLEANSING_INFO, STRUCTURING_INFO) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
    }
    if isinstance(params, list):  # 벌크 삽입(벌크 입력은 return_id 지원 안함)
        print("bulk insert execute", params)
        return execute_many(map[key], params_list=params)
    elif isinstance(params, tuple):  # 단일 삽입
        print("insert execute", params)
        return execute(map[key], params=params, fetch=fetch, return_id=return_id)
    else:
        print("error", "파라미터가 list나 tuple이 아닙니다.")
        raise ValueError("파라미터가 list나 tuple이 아닙니다.")


def update_map(key, params: tuple = None):
    map = {
        "updateDocClass": "UPDATE TB_DI_DOC_CLASS SET DOC_NM=%s, UPDT=current_timestamp() WHERE DOC_CLASS_ID=%s ",
        "updateLayoutClass": "UPDATE TB_DI_LAYOUT_CLASS SET LAYOUT_NM=%s, DOC_CLASS_ID=%s, LAYOUT_DESC=%s, LAYOUT_ORDR=%s, IMG_PREPROCESS_INFO=%s, CLASSIFY_AI_INFO=%s, UPDT=current_timestamp() WHERE LAYOUT_CLASS_ID=%s",
        "updateLayoutClassTemplateFilePath": "UPDATE TB_DI_LAYOUT_CLASS SET TEMPLATE_FILE_PATH=%s WHERE LAYOUT_CLASS_ID=%s ",
    }
    print(" query : ", map[key], params)
    execute(map[key], params=params, fetch=False)


def check_map(key, params: tuple = None):
    map = {
        "checkExsDocClass": "SELECT COUNT(*) FROM TB_DI_DOC_CLASS A WHERE A.DOC_CLASS_ID= %s ",
        "checkDelDocClass": "SELECT COUNT(*) FROM TB_DI_LAYOUT_CLASS A WHERE A.DOC_CLASS_ID= %s ",
        "checkDelLayoutClass": "SELECT COUNT(*) FROM TB_DI_SECTION_CLASS WHERE LAYOUT_CLASS_ID= %s",
        # 다른 check 쿼리들은 필요에 따라 추가
    }
    print(" query : ", map[key], params)
    result = execute(map[key], params=params, fetch=True)
    print("result : ", result)
    return result[0][0]  # 값 1개만 반환


def delete_map(key, params: tuple = None):
    map = {
        "deleteDocClass": "DELETE FROM TB_DI_DOC_CLASS WHERE DOC_CLASS_ID=%s ",
        "deleteLayoutClass": "DELETE FROM TB_DI_LAYOUT_CLASS WHERE LAYOUT_CLASS_ID=%s",
        # 다른 delete 쿼리들은 필요에 따라 추가
    }
    print(" query : ", map[key], params)
    execute(map[key], params=params, fetch=False)


def select_list_map(key, params: tuple = None, dictionary: bool = False):
    map = {
        "selectOprtnSetList": (
            "SELECT A.OPRTN_SET_ID, A.OPRTN_CD, A.OPRTN_SET_NM, A.OPRTN_SET_DESC, A.OPRTN_SET_ORDR "
                "FROM TB_DS_OPRTN_SET AS A "
                "WHERE A.OPRTN_CD = %s "
                "ORDER BY A.OPRTN_SET_ORDR, A.OPRTN_SET_ID ",
            ['oprtn_set_id', 'oprtn_cd', 'oprtn_set_nm', 'oprtn_set_desc', 'oprtn_set_ordr']
        ),  
        "selectDocClassList": (
            "SELECT A.DOC_CLASS_ID, A.DOC_NM, A.RGDT, A.UPDT "
                "FROM TB_DI_DOC_CLASS AS A "
                "WHERE A.DOC_NM LIKE %s "
                "ORDER BY A.DOC_CLASS_ID ",
            ['doc_class_id', 'doc_name', 'rgdt', 'updt']
        ),
        "selectLayoutClassList": (
            "SELECT A.LAYOUT_CLASS_ID, A.DOC_CLASS_ID, A.LAYOUT_NM, A.LAYOUT_DESC, A.LAYOUT_ORDR, "
                "A.RGDT, A.UPDT, CONCAT(B.DOC_NM, ' <', A.DOC_CLASS_ID, '>') AS DOC_CLASS_INFO "
                "FROM TB_DI_LAYOUT_CLASS A INNER JOIN TB_DI_DOC_CLASS B ON A.DOC_CLASS_ID=B.DOC_CLASS_ID "
                "WHERE A.LAYOUT_NM LIKE %s "
                "ORDER BY A.LAYOUT_ORDR, A.LAYOUT_CLASS_ID",
            ['layout_class_id', 'doc_class_id', 'layout_name', 'layout_desc', 'layout_order', 'rgdt', 'updt', 'doc_class_info']
        ),
        "selectSectionClass": (
            "SELECT A.SECTION_CLASS_ID, A.LAYOUT_CLASS_ID, A.SECTION_NM, A.SECTION_DESC, A.SEPARATE_SECTION_INFO, "
                "A.SEPARATE_BLOCK_INFO, A.OCR_INFO, A.CLEANSING_INFO, A.RGDT, A.UPDT, "
                "A.SECTION_ORDR, A.STRUCTURING_INFO, A.SECTION_TYPE "
                "FROM TB_DI_SECTION_CLASS A "
                "WHERE A.LAYOUT_CLASS_ID = %s "
                "ORDER BY A.SECTION_ORDR, A.SECTION_CLASS_ID",
            ['section_class_id','layout_class_id','section_name','section_desc','separate_section_info','separate_block_info','ocr_info','cleansing_info','rgdt','updt','section_ordr','structuring_info','section_type']
        ),
        "selectCodeList": (
            "SELECT A.CD, A.CD_GRP, A.CD_NM, A.CD_VAL, A.CD_DESC, A.CD_ORDR "
                "FROM TB_CO_CODE A "
                "WHERE A.CD_GRP = %s and use_yn = 'Y' "
                "ORDER BY A.CD_ORDR, A.CD",
            ['cd','cd_grp','cd_nm','cd_val','cd_desc','cd_ordr']
        ),

        # 기타 기존 쿼리들...
    }
    print(" query : ", map[key][0], params)
    result = execute(map[key][0], params=params, fetch=True, dictionary=dictionary)
    print("result : ", result)
    if dictionary:
        return result
    else:
        return tuples_to_dicts(result, map[key][1])


def select_row_map(key, params: tuple = None, dictionary: bool = False):
    map = {
        "selectDocClass": (
            "SELECT A.DOC_CLASS_ID, A.DOC_NM, A.RGDT, A.UPDT "
                "FROM TB_DI_DOC_CLASS AS A "
                "WHERE A.DOC_CLASS_ID = %s ",
            ['doc_class_id', 'doc_name', 'rgdt', 'updt']
        ),
        "selectLayoutClass": (
            "SELECT A.LAYOUT_CLASS_ID, A.DOC_CLASS_ID, A.LAYOUT_NM, A.LAYOUT_DESC, A.LAYOUT_ORDR, "
                "A.IMG_PREPROCESS_INFO, A.CLASSIFY_AI_INFO, A.TEMPLATE_FILE_PATH, A.RGDT, A.UPDT, "
                "CONCAT(B.DOC_NM, '(', A.DOC_CLASS_ID, ')') AS DOC_CLASS_INFO "
                "FROM TB_DI_LAYOUT_CLASS A INNER JOIN TB_DI_DOC_CLASS B ON A.DOC_CLASS_ID=B.DOC_CLASS_ID "
                "WHERE A.LAYOUT_CLASS_ID = %s",
            ['layout_class_id', 'doc_class_id', 'layout_name', 'layout_desc', 'layout_order', 'img_preprocess_info', 'classify_ai_info', 'template_file_path','rgdt', 'updt', 'doc_class_info']
        ),
        "selectOprtnSetInfo": (
            "SELECT A.STEP_LIST "
                "FROM TB_DS_OPRTN_SET AS A "
                "WHERE A.OPRTN_SET_ID = %s "
                "ORDER BY A.OPRTN_SET_ORDR, A.OPRTN_SET_ID ",
            ['step_list']
        ),
    }
    print(" query : ", map[key][0], params)
    result = execute(map[key][0], params=params, fetch=True, dictionary=dictionary)
    print("result : ", result)
    if dictionary:
        return result
    else:
        return tuples_to_dicts(result, map[key][1])[0] if result else None  # 값이 없으면 None 반환


def select_one_map(key, params: tuple = None):
    map = {
        # "selectPatternInfo":"SELECT A.FORMAT_INFO "+
        #          "FROM TB_DS_COLUMN A INNER JOIN TB_DI_BLOCK_CLASS B ON A.COLUMN_ID=B.COLUMN_ID "+
        #          "WHERE B.SECTION_CLASS_ID = %s AND BLOCK_ROW_NUM= %s AND BLOCK_COL_NUM = %s "+
        #          "ORDER BY B.BLOCK_CLASS_ID DESC LIMIT 1 ",
        # "selectBlockCrctnMatched":"SELECT A.CRRCT_TEXT  "+
        #          "FROM TB_DI_BLOCK_CRCTN A INNER JOIN TB_DI_BLOCK_CLASS B ON A.BLOCK_CLASS_ID=B.BLOCK_CLASS_ID "+
        #          "WHERE B.SECTION_CLASS_ID=%s AND B.BLOCK_ROW_NUM=%s AND B.BLOCK_COL_NUM=%s AND A.ERROR_TEXT=%s " +
        #          "ORDER BY CRCTN_ORDR DESC LIMIT 1 ",
    }
    print(" query : ", map[key], params)
    result = execute(map[key], params=params, fetch=True)
    if result:
        print("result : ", result[0][0])
        return result[0][0]  # 값 1개만 반환
    else:
        return None 


# 공통
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
# def select_doc_class_id(params:list) -> int:
#     if not params and len(params) == 0:
#         return None
#     placeholders = ','.join(['%s'] * len(params)) 
#     query = f"""
#         SELECT DOC_CLASS_ID FROM VW_DI_DOC_LAYOUT_SECTION 
#          WHERE LAYOUT_CLASS_ID IN ({placeholders}) 
#          GROUP BY DOC_CLASS_ID ORDER BY COUNT(*) DESC 
#          FETCH FIRST 1 ROW ONLY 
#     """
#     print(" query : ",query, params)
#     result = execute(query, params=params, fetch=True)
#     if result:
#         return result[0][0]  # 값 1개만 반환
#     else:
#         return None 