from flask_appbuilder import BaseView as AppBuilderBaseView, expose, has_access
from flask import request, flash, redirect
from sqlalchemy import create_engine, text
from flask_appbuilder._compat import as_unicode
from flask_appbuilder.const import FLAMSG_ERR_SEC_ACCESS_DENIED
from flask_appbuilder.models.filters import BaseFilterConverter, Filters
from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    DateTimeField,
    DecimalField,
    FloatField,
    IntegerField,
    StringField,
    TextAreaField,
)
from wtforms.validators import DataRequired
from airflow.configuration import conf
from typing import Any, Type, List, Dict, Optional

PAGE_SIZE = conf.getint("webserver", "page_size")
class FormManageModelView(AppBuilderBaseView):
    template_folder = "/opt/airflow/plugins/form_manage_plugin/templates"
    default_page_size = PAGE_SIZE

    @expose("/list/")
    @has_access
    def list(self):
        pass
    
    @expose("/show/<pk>", methods=["GET"])
    @has_access
    def show(self, pk):
        pass
    
    @expose("/add", methods=["GET", "POST"])
    @has_access
    def add(self):
        pass

    @expose("/edit/<pk>", methods=["GET", "POST"])
    @has_access
    def edit(self, pk):
        pass
    
    @expose("/delete/<pk>", methods=["GET", "POST"])
    @has_access
    def delete(self, pk):
        pass
    
    def create_form(
        self,
        label_columns=None,
        inc_columns=None,
        description_columns=None,
        validators_columns=None,
    ):
        label_columns = label_columns or {} # 편집 폼의 라벨 목록
        inc_columns = inc_columns or [] # 편집 가능 필드 목록
        description_columns = description_columns or {} # 편집 폼의 설명 목록
        validators_columns = validators_columns or {} # 편집 폼의 유효성 검사 목록
        form_props = {}
        for col_name in inc_columns:
            self._convert_col(
                col_name,
                self._get_label(col_name, label_columns),
                self._get_description(col_name, description_columns),
                self._get_validators(col_name, validators_columns),
                self.edit_form_query_rel_fields,
                form_props,
            )
    def _convert_col(
        self,
        col_name,
        label,
        description,
        validators,
        query_rel_fields,
        form_props,
    ):
        conversion_table = (
            ("image", ImageUploadField, BS3ImageUploadFieldWidget),
            ("file", FileUploadField, BS3FileUploadFieldWidget),
            ("gridfs_file", MongoFileField, BS3FileUploadFieldWidget),
            ("gridfs_image", MongoImageField, BS3ImageUploadFieldWidget),
            ("text", TextAreaField, BS3TextAreaFieldWidget),
            ("binary", TextAreaField, BS3TextAreaFieldWidget),
            ("string", StringField, BS3TextFieldWidget),
            ("integer", IntegerField, BS3TextFieldWidget),
            ("numeric", DecimalField, BS3TextFieldWidget),
            ("float", FloatField, BS3TextFieldWidget),
            ("boolean", BooleanField, None),
            ("date", DateField, DatePickerWidget),
            ("datetime", DateTimeField, DateTimePickerWidget),
        )
        # 기본적으로 StringField로 변환
        form_props[col_name] = StringField(label, description=description, validators=validators)
        return form_props
    
    
    def prefill_show(self, item):
        """
        이 메서드를 재정의하세요. 현재 액션이 상세 보기 폼 렌더링(GET 요청)일 때만 호출되며,
        폼을 미리 채우기 위해 추가 작업을 수행할 때 사용됩니다.

        데이터베이스 내용에 따라 달라지는 커스텀 필드를 추가했을 때 유용합니다.
        일반 컬럼이나 관계 이름으로 추가된 필드는 기본적으로 잘 작동합니다.

        예시:
        def prefill_show(self, item):
            if item.email:
                item.email_confirmation = item.email
        """

    def prefill_form(self, form, pk):
        """
        이 메서드를 재정의하세요. 현재 액션이 편집 폼 렌더링(GER 요청)일 때만 호출되며,
        폼을 미리 채우기 위해 추가 작업을 수행할 때 사용됩니다.

        데이터베이스 내용에 따라 달라지는 커스텀 필드를 추가했을 때 유용합니다.
        일반 컬럼이나 관계 이름으로 추가된 필드는 기본적으로 잘 작동합니다.

        예시:
        def prefill_form(self, form, pk):
            if form.email.data:
                form.email_confirmation.data = form.email.data
        """

    def process_form(self, form, is_created):
        """
        이 메서드를 재정의하세요. 현재 액션이 생성/수정 폼 제출(POST 요청)일 때만 호출되며,
        폼 데이터를 아이템에 채우기 전에 추가 작업을 수행할 때 사용됩니다.

        기본 동작은 아무 작업도 하지 않습니다.

        예시:

        def process_form(self, form, is_created):
            if not form.owner:
                form.owner.data = 'n/a'
        """

    def pre_update(self, item):
        """
        이 메서드를 재정의하세요. 업데이트가 실행되기 전에 호출됩니다.
        이 메서드에서 예외가 발생하면, 메시지가 사용자에게 보여지고 업데이트 작업은 중단됩니다.
        이 특성을 활용해 업데이트에 대해 더 복잡한 로직을 구현할 수 있습니다.
        예를 들어, 오브젝트의 원래 생성자만 업데이트를 허용하는 경우 등입니다.
        """

    def post_update(self, item):
        """
        이 메서드를 재정의하세요. 업데이트가 완료된 후에 호출됩니다.
        """

    def pre_add(self, item):
        """
        이 메서드를 재정의하세요. 추가(생성) 작업 전에 호출됩니다.
        이 메서드에서 예외가 발생하면, 메시지가 사용자에게 보여지고 추가 작업은 중단됩니다.
        """

    def post_add(self, item):
        """
        이 메서드를 재정의하세요. 추가(생성) 작업 후에 호출됩니다.
        """

    def pre_delete(self, item):
        """
        이 메서드를 재정의하세요. 삭제 작업 전에 호출됩니다.
        이 메서드에서 예외가 발생하면, 메시지가 사용자에게 보여지고 삭제 작업은 중단됩니다.
        이 특성을 활용해 삭제에 대해 더 복잡한 로직을 구현할 수 있습니다.
        예를 들어, 오브젝트의 원래 생성자만 삭제를 허용하는 경우 등입니다.
        """

    def post_delete(self, item):
        """
        이 메서드를 재정의하세요. 삭제 작업 후에 호출됩니다.
        """

    def post_edit_redirect(self):
        """Override this function to control the
        redirect after edit endpoint is called."""
        return redirect(self.get_redirect())

# class FormManageFilter(object):
#     def get_columns_list(self):
#         return []


class DynamicForm(FlaskForm):
    """
    Refresh method will force select field to refresh
    """
    doc_name = StringField("문서 이름", validators=[DataRequired()])
    is_active = BooleanField("활성화 여부")

    @classmethod
    def refresh(self, obj=None):
        form = self(obj=obj)
        return form
