from PIL import Image
import json
from typing import Any
import os
import traceback
from airflow.models import Variable
from markupsafe import Markup
from flask import current_app, g, redirect, url_for, request, Response, abort, flash, send_from_directory
from flask_appbuilder import expose, has_access
from flask_appbuilder.widgets import FormWidget, SearchWidget, ShowWidget
from flask_appbuilder.actions import action
from flask_appbuilder.utils.base import get_safe_redirect, lazy_formatter_gettext
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_appbuilder.urltools import get_order_args, get_page_args, get_page_size_args
from flask_babel import lazy_gettext as _, force_locale
from sqlalchemy import inspect, text
from plugins.form_manage_plugin.views.general.form_manage_base_view import DynamicForm, FormManageModelView
from plugins.form_manage_plugin.util.db import manage_query_util
from plugins.form_manage_plugin.util.validator import wtforms_validator as custom_validators
from airflow.providers.fab.auth_manager.models import User
from wtforms import validators
from dags.utils.img import type_convert_util

OPER_SEPARATE_SECTION_DEFAULT = Variable.get("OPER_SEPARATE_SECTION_DEFAULT", default_var="2")
OPER_CREATE_AI_DEFAULT = Variable.get("OPER_CREATE_AI_DEFAULT", default_var="11")
OPER_OCR_DEFAULT = Variable.get("OPER_OCR_DEFAULT", default_var="7")
OPER_CLEANSING_DEFAULT = Variable.get("OPER_CLEANSING_DEFAULT", default_var="8")
OPER_STRUCTURING_DEFAULT = Variable.get("OPER_STRUCTURING_DEFAULT", default_var="9")

CLASS_FOLDER = Variable.get("CLASS_FOLDER", default_var="/opt/airflow/data/class")
class LayoutClassManageView(FormManageModelView):
    route_base = "/layout"
    endpoint = "layout"   

    # 타이틀
    list_title = _("레이아웃 목록")
    show_title = _("레이아웃 상세")
    add_title = _("레이아웃 추가")
    edit_title = _("레이아웃 수정")

    # 템플릿 경로
    list_template = "form/layout/layout_list.html"
    show_template = "form/layout/layout_show.html"
    add_template = "form/layout/layout_add.html"
    edit_template = "form/layout/layout_edit.html"
    section_add_template = "form/layout/layout_section_add.html"
    section_edit_template = "form/layout/layout_section_edit.html"

    # 공통정보
    label_columns = {
        "layout_name": _("레이아웃명"),
        "doc_class_id": _("문서서식ID"),
        "doc_class_info": _("문서서식"),
        "layout_desc": _("설명"),
        "layout_order": _("순서"),
        "img_preprocess_info": _("이미지 전처리 정보"),
        "classify_ai_info": _("분류 AI 정보"),
        "rgdt": _("생성일"),
        "updt": _("수정일"),
    }
    def text_formatter(value):
        if value is not None:
            return Markup('<span>{value}</span>').format(value=value)
        else:
            return Markup('<span class="label label-danger">Invalid</span>')
    
    formatters_columns = {}

    #입력(등록/수정) 폼 정보
    description_columns = {
        "layout_name": _("레이아웃 이름을 입력하세요."),
        "doc_class_id": _("연결된 문서서식 ID를 입력하세요."),
        "layout_desc": _("레이아웃 설명"),
        "layout_order": _("레이아웃 순서"),
        "img_preprocess_info": _("이미지 전처리 관련 세부 정보 입력"),
        "classify_ai_info": _("AI 분류 정보 입력"),
    }
    type_columns = {
        "layout_name": "string",
        "doc_class_id": "integer",
        "doc_class_info": "string",
        "layout_desc": "string",
        "layout_order": "integer",
        "img_preprocess_info": "text",
        "classify_ai_info": "text",
        "rgdt": "datetime",
        "updt": "datetime",
    }
    validators_columns = {
        "layout_name": [validators.DataRequired()],
        "doc_class_id": [validators.DataRequired()],
        "img_preprocess_info": [custom_validators.JsonValidator()],
        "classify_ai_info": [custom_validators.JsonValidator()],
    }
    default_columns = {
        "layout_name": "",
        "doc_class_id": None,
        "layout_desc": "",
        "layout_order": 0,
        "img_preprocess_info": "",
        "classify_ai_info": "",
    }

    
    # 목록정보
    list_columns = [
        "doc_class_info", "layout_name", "layout_desc", 
        "layout_order", "rgdt", "updt"
    ]

    search_columns = list_columns
    show_columns = [
        "layout_name", "doc_class_info", "layout_desc", 
        "layout_order", "img_preprocess_info", "classify_ai_info",
        "rgdt", "updt"
    ]
    add_columns = [
        "layout_name", "doc_class_id", "layout_desc", 
        "layout_order", "img_preprocess_info", "classify_ai_info"
    ]
    edit_columns = [
        "layout_name", "doc_class_id", "layout_desc", 
        "layout_order", "img_preprocess_info", "classify_ai_info"
    ]

    add_exclude_cols = []
    edit_exclude_cols = []

    @expose("/list/")
    @has_access
    def list(self):
        print("layout list")
        layout_name_like = request.args.get("layout_name_like", "")
        value_columns = manage_query_util.select_list_map("selectLayoutClassList", (f"%{layout_name_like}%",))
        actions = {}  # 체크박스 관련 기능 정의

        page = self.default_page_size

        if value_columns:
            pk_col = list(value_columns[0].keys())[0]  # 첫 번째 dict의 첫 번째 키
            pks = [row[pk_col] for row in value_columns]
        else:
            pk_col = None
            pks = []
        count = len(value_columns)
        self.update_redirect()
        return self.render_template(
            self.list_template,
            appbuilder=self.appbuilder,
            title=self.list_title,
            label_columns=self.label_columns,
            include_columns=self.list_columns,
            formatters_columns=self.formatters_columns,
            value_columns=value_columns,  # 실제값
            page=page,
            page_size=self.default_page_size,
            count=count,
            pks=pks,
            actions=actions,
            modelview_name=self.__class__.__name__,
        )

    @expose("/add", methods=["GET", "POST"])
    @has_access
    def add(self):
        print("layout add")
        if request.method == "POST":
            item = {}
            try:
                for key, value in request.form.items():
                    item[key] = value
            except Exception as e:
                print("에러 메시지:", e)
                traceback.print_exc()
            else:
                param = (
                    item["doc_class_id"],
                    item["layout_name"],
                    item.get("layout_desc", ""),
                    item.get("layout_order", 0),
                    item["img_preprocess_info"],
                    item["classify_ai_info"],
                )
                manage_query_util.insert_map("insertLayoutClass", param)  # insert 쿼리 실행
                #추가 전 입력 데이터 유효성 체크
                doc_class_id = item.get("doc_class_id")
                result = manage_query_util.check_map("checkExsDocClass", (doc_class_id,))
                if result <= 0:
                    raise Exception("DocClassId가 존재하지 않습니다.")
                flash("정상적으로 처리되었습니다.", "success")
                return self.post_action_redirect()  # 수정 후 이전 화면으로 이동
        self.update_redirect()
        return self.render_template(
            self.add_template,
            title=self.add_title,
            doc_class_list=manage_query_util.select_list_map("selectDocClassList",("%%",)),
            img_preprocess_list=manage_query_util.select_list_map("selectOprtnSetList",("P002",)),
            classify_ai_list=manage_query_util.select_list_map("selectOprtnSetList",("P002",)),
        )

    @expose("/show/<pk>", methods=["GET"])
    @has_access
    def show(self, pk):
        item = manage_query_util.select_row_map("selectLayoutClass", (pk,))
        if not item:
            abort(404)
        self.prefill_show(item)
        self.update_redirect()
        return self.render_template(
            self.show_template,
            title=self.show_title,
            item=item,
        )

    @expose("/edit/<pk>", methods=["GET", "POST"])
    @has_access
    def edit(self, pk):
        if request.method == "POST":
            print("POST method")
            try:
                for key, value in request.form.items():
                    item[key] = value
                self.pre_update(item)
            except Exception as e:
                print("에러 메시지:", e)
                traceback.print_exc()
            else:
                param = (
                    item["layout_name"],
                    item["doc_class_id"],
                    item.get("layout_desc", ""),
                    item.get("layout_order", 0),
                    item["img_preprocess_info"],
                    item["classify_ai_info"],
                    item["layout_class_id"],
                )
                manage_query_util.update_map("updateLayoutClass", param)  # update 쿼리 실행
                flash("정상적으로 처리되었습니다.", "success")
                return self.post_action_redirect()
        item = manage_query_util.select_row_map("selectLayoutClass", (pk,))
        if not item:
            abort(404)
        self.update_redirect()
        return self.render_template(
            self.edit_template,
            title=self.edit_title,
            item=item,
            doc_class_list=manage_query_util.select_list_map("selectDocClassList",("%%",)),
            img_preprocess_list=manage_query_util.select_list_map("selectOprtnSetList",("P002",)),
            classify_ai_list=manage_query_util.select_list_map("selectOprtnSetList",("P002",)),
        )

    @expose("/delete/<pk>", methods=["POST"])
    @has_access
    def delete(self, pk):
        item = manage_query_util.select_row_map("selectLayoutClass", (pk,))
        if not item:
            abort(404)
        try:
            #삭제 전 대상 데이터 삭제 가능 여부 체크
            layout_class_id = item.get("layout_class_id")
            result = manage_query_util.check_map("checkDelLayoutClass", (layout_class_id,))
            if result > 0:
                raise Exception("연관된 데이터가 존재하는 레이아웃은 삭제할 수 없습니다.")
        except Exception as e:
            print("에러 메시지:", e)
            traceback.print_exc()
        else:
            param = (item["layout_class_id"],)
            manage_query_util.delete_map("deleteLayoutClass", param)  # delete 쿼리 실행
            flash("정상적으로 처리되었습니다.", "success")
            self.update_redirect()
        return self.post_action_redirect()
        
    @expose("/section/<pk>", methods=["GET", "POST"])
    @has_access
    def section(self,pk):
        print("layout section")
        if request.method == "POST":
            print("post method")
            item = {}
            try:
                for key, value in request.form.items():
                    item[key] = value
                file = request.files.get("templateFile")
                print(file.filename)
                layout_class_id = item.get("layoutClassId")
                if file:
                    class_template_folder_path = os.path.join(CLASS_FOLDER,item.get("docClassId"),layout_class_id,"classify","template")
                    print(os.path.abspath(class_template_folder_path))
                    os.makedirs(class_template_folder_path, exist_ok=True)
                    class_template_file_path = os.path.join(class_template_folder_path,file.filename)
                    print(class_template_folder_path)
                    file.save(class_template_file_path)
                    manage_query_util.update_map("updateLayoutClassTemplateFilePath", (class_template_file_path,layout_class_id))
            except Exception as e:
                print("에러 메시지:", e)
                traceback.print_exc()
                result_json = {"status": "error", "message": str(e)}
                json_str = json.dumps(result_json, ensure_ascii=False)
                return Response(json_str, mimetype="application/json") # ajax 리턴
            else:
                num = 0
                item.get("deleteSecClassIds",[])
                
                section_list = json.loads(item.get("sectionList", "[]"))
                for section in section_list:
                    num += 1
                    obj_id = section.get("id")
                    rect = section.get("rect")
                    section_name = section.get("sectionName","")
                    section_type = section.get("sectionType","")
                    separate_block_oprtn_set_id = section.get("separateBlockType","{}")
                    separate_section_info = _get_separate_section_info(section_name, class_template_file_path, rect)
                    separate_block_info = _get_separate_block_info(section_name, separate_block_oprtn_set_id)
                    ocr_info = _get_ocr_info(section_name)
                    cleansing_info = _get_cleansing_info(section_name)
                    structuring_info = _get_structuring_info(section_name)                 
                    
                    param = (
                        layout_class_id,
                        section_name,
                        section_name,
                        section_type,
                        num,
                        separate_section_info,
                        separate_block_info,
                        ocr_info,
                        cleansing_info,
                        structuring_info
                    )
                    manage_query_util.insert_map("insertSection", param)  # insert 쿼리 실행
                result_json = {"status": "success", "redirect_url": self.get_redirect()}
                json_str = json.dumps(result_json, ensure_ascii=False)
                return Response(json_str, mimetype="application/json") # ajax 리턴
        item = manage_query_util.select_row_map("selectLayoutClass", (pk,))
        if not item:
            abort(404)
        self.update_redirect()
        if item.get("template_file_path") is None:
            print
            return self.render_template(
                self.section_add_template,
                title=self.add_title,
                item=item,
                doc_class_list=manage_query_util.select_list_map("selectDocClassList",("%%",)),
                section_type_list=manage_query_util.select_list_map("selectCodeList",("sect_type",)),
                separate_block_list=manage_query_util.select_list_map("selectOprtnSetList",("P032",)),
                img_preprocess_list=manage_query_util.select_list_map("selectOprtnSetList",("P011",)),
                classify_ai_list=manage_query_util.select_list_map("selectOprtnSetList",("P012",)),
            )
        else:
            return self.render_template(
                self.section_add_template,
                title=self.edit_title,
                item=item,
                doc_class_list=manage_query_util.select_list_map("selectDocClassList",("%%",)),
                section_type_list=manage_query_util.select_list_map("selectCodeList",("sect_type",)),
                separate_block_list=manage_query_util.select_list_map("selectOprtnSetList",("P032",)),
                img_preprocess_list=manage_query_util.select_list_map("selectOprtnSetList",("P011",)),
                classify_ai_list=manage_query_util.select_list_map("selectOprtnSetList",("P012",)),
            )
    @expose("/load/<pk>", methods=["GET"])
    @has_access
    def load(self,pk):
        item = manage_query_util.select_row_map("selectLayoutClass", (pk,))
        if item:
            url = type_convert_util.convert_type(item["template_file_path"],"file_path","url")
            rectList = []
            section_list = manage_query_util.select_list_map("selectSectionClass", (pk,))
            for section_info in section_list:
                separate_section_info = json.loads(section_info["separate_section_info"])
                separate_block_info = json.loads(section_info["separate_block_info"])
                section_data = {
                    "sectionClassId": section_info["section_class_id"],
                    "rect": separate_section_info.get("rect",[]),
                    "sectionName": section_info["section_name"],
                    "sectionType": section_info["section_type"],
                    "separateBlockType": separate_block_info.get("block_type",""),
                }
                rectList.append(section_data)
            result_json = {"status": "success", "imageUrl":url,"regions": rectList}
            json_str = json.dumps(result_json, ensure_ascii=False)
            return Response(json_str, mimetype="application/json") # ajax 리턴
        else:
            result_json = {"status": "error", "message": str("조회 대상이 없습니다.")}
            json_str = json.dumps(result_json, ensure_ascii=False)
            return Response(json_str, mimetype="application/json") # ajax 리턴
            

        
def _get_separate_section_info(section_name, file_path, obj_box):
    # 이미지 열기
    with Image.open(file_path) as img:
        img_w, img_h = img.size  # 실제 이미지 가로, 세로

    if isinstance(obj_box, dict):
        x = obj_box.get('x', 0)
        y = obj_box.get('y', 0)
        w = obj_box.get('w', 0)
        h = obj_box.get('h', 0)
    else:
        x, y, w, h = obj_box

    # 100 기준으로 비율 계산(센터 톱 기준)
    ratio_x = ((x / img_w) * 100)-50 if img_w else 0
    ratio_y = (y / img_h) * 100 if img_h else 0
    ratio_w = (w / img_w) * 100 if img_w else 0
    ratio_h = (h / img_h) * 100 if img_h else 0

    area_ratio = [ratio_x, ratio_y, ratio_w, ratio_h]
    separate_section_info = {"name":section_name,"type":"separate_area_step_list","rect":obj_box}
    row = manage_query_util.select_row_map("selectOprtnSetInfo", (OPER_SEPARATE_SECTION_DEFAULT,))
    separate_section_step_list = json.loads(row["step_list"])
    separate_section_step_list[0]["param"]["area_ratio"] = area_ratio
    separate_section_step_list[0]["param"]["area_name"] = section_name
    separate_section_info["step_list"] = separate_section_step_list
    return separate_section_info
    

def _get_separate_block_info(section_name, block_type):
    separate_block_info = {"name":section_name,"type":"separate_block_step_list","block_type":block_type}
    separate_block_setp_list = manage_query_util.select_row_map("selectOprtnSetInfo", (block_type,))
    separate_block_info["step_list"] = separate_block_setp_list
    return separate_block_info
def _get_ocr_info(section_name):
    ocr_info = {"name":section_name,"type":"ocr_step_list"}
    ocr_setp_list = ocr_info = manage_query_util.select_row_map("selectOprtnSetInfo", (OPER_OCR_DEFAULT,))
    ocr_info["step_list"] = ocr_setp_list
    return ocr_info
def _get_cleansing_info(section_name):
    cleansing_info = {"name":section_name,"type":"cleansing_step_list"}
    cleansing_step_list = manage_query_util.select_row_map("selectOprtnSetInfo", (OPER_CLEANSING_DEFAULT,))
    cleansing_info["step_list"] = cleansing_step_list
    return cleansing_info
def _get_structuring_info(section_name):
    structuring_info = {"name":section_name,"type":"cleansing_step_list"}
    structuring_setp_list = manage_query_util.select_row_map("selectOprtnSetInfo", (OPER_STRUCTURING_DEFAULT,))
    structuring_info["step_list"] = structuring_setp_list
    return structuring_info
