from typing import Any
from flask import current_app, g, redirect, url_for, request, abort
from flask_appbuilder import expose, has_access
from flask_appbuilder.widgets import FormWidget, SearchWidget, ShowWidget
from flask_appbuilder.actions import action
from flask_appbuilder.utils.base import get_safe_redirect, lazy_formatter_gettext
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_appbuilder.urltools import get_order_args, get_page_args, get_page_size_args
from flask_babel import _, lazy_gettext, force_locale
from sqlalchemy import inspect, text
from werkzeug.wrappers import Response as WerkzeugResponse
from plugins.form_manage_plugin.views.form_manage_base_view import DynamicForm, FormManageModelView
from plugins.form_manage_plugin.util.db import manage_query_util
from airflow.providers.fab.auth_manager.models import User


def _roles_custom_formatter(string: str) -> str:
    if current_app.config.get("AUTH_ROLES_SYNC_AT_LOGIN", False):
        string += (
            ". <div class='alert alert-warning' role='alert'>"
            "AUTH_ROLES_SYNC_AT_LOGIN is enabled, changes to this field will "
            "not persist between user logins."
            "</div>"
        )
    return string

class DocClassManageView(FormManageModelView):
    route_base = "/doc"
    endpoint = "doc"   

    list_title = _("Doc Template List")
    show_title = _("Doc Template Details")
    add_title = _("Add Doc Template")
    edit_title = _("Edit Doc Template")

    #공통정보
    label_columns = {
        "doc_name": _("Doc Template Name"),
        "rgdt": _("Created on"),
        "updt": _("Changed on"),
    }
    description_columns = {
        "doc_name": _("Enter a Doc Name For Distinction."),
    }
    
    #목록정보
    list_columns = ["doc_name", "rgdt", "updt"]
    formatters_columns = {}
    search_columns = [
        "doc_name",
        "rgdt",
        "updt",
    ]
    #상세정보
    show_columns = ["doc_name", "rgdt", "updt"]
    show_fieldsets = [
        (
            lazy_gettext("Doc Info"),
            {"fields": ["doc_name"]},
        )
    ]
    #입력정보
    form_columns = ["doc_name"]
    form_fieldsets = [
        (
            lazy_gettext("Doc Info"),
            {"fields": ["doc_name"]},
        )
    ]
    validators_columns = {}
    add_form_extra_fields = {}
    edit_form_extra_fields = {}
    add_form_query_rel_fields = {}
    edit_form_query_rel_fields = {}
    

    add_columns = ["doc_name"]
    edit_columns = ["doc_name"]
    
    def _init_forms(self):
        """
        Init forms for Add and Edit
        """
        if not self.add_form:
            self.add_form = self.create_form(
                self.label_columns,
                self.add_columns,
                self.description_columns,
                self.validators_columns,
                self.add_form_extra_fields,
                self.add_form_query_rel_fields,
            )
        if not self.edit_form:
            
            self.edit_form = type("DynamicForm", (DynamicForm,), form_props)

    @expose("/list/")
    @has_access
    def list(self):
        doc_name_like = request.args.get("doc_name_like", "")
        value_columns = manage_query_util.select_list_map("selectDocClassList",(f"%{doc_name_like}%",))
        actions = {} # 체크박스 관련 기능 정의
        
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
            "form/doc/doc_list.html",
            appbuilder=self.appbuilder,
            title=self.list_title,
            label_columns=self.label_columns,
            include_columns=self.list_columns,
            formatters_columns=self.formatters_columns,
            value_columns=value_columns, #실제값
            page=page,
            page_size=self.default_page_size,
            count=count,
            pks=pks,
            actions=actions,
            modelview_name=self.__class__.__name__,
        )
    
    @expose("/show/<pk>", methods=["GET"])
    @has_access
    def show(self, pk):
        widgets = self._show(pk)
        return self.render_template(
            "form/doc/doc_show.html",
            pk=pk,
            title=self.show_title,
            widgets=widgets,
        )
    def _show(self, pk):
        # pages = get_page_args()
        # page_sizes = get_page_size_args()
        # orders = get_order_args()
        item = manage_query_util.select_row_map("selectDocClass",(pk,))
        if not item:
            abort(404)
        self.prefill_show(item)
        
        widgets = {}
        actions = {}
        show_fieldsets = self.show_fieldsets
        value_columns = [item[col] for col in self.show_columns]
        widgets["show"] = ShowWidget(
            pk=pk,
            label_columns=self.label_columns,
            include_columns=self.show_columns,
            value_columns=value_columns,
            formatters_columns=self.formatters_columns,
            actions=actions,
            fieldsets=show_fieldsets,
            modelview_name=self.__class__.__name__,
        )
        self.update_redirect()
        return widgets
    
    @expose("/edit/<pk>", methods=["GET", "POST"])
    @has_access
    def edit(self, pk):
        """
        Edit view.

        Same implementation as
        https://github.com/dpgaspar/Flask-AppBuilder/blob/1c3af9b665ed9a3daf36673fee3327d0abf43e5b/flask_appbuilder/views.py#L602

        Override it to use a custom ``has_access_with_pk`` decorator to take into consideration resource for
        fined-grained access.
        """
        widgets = self._edit(pk)
        if not widgets:
            return self.post_edit_redirect()
        else:
            return self.render_template(
                self.edit_template,
                title=self.edit_title,
                widgets=widgets,
            )
    def _edit(self, pk):
        """
        Edit function logic, override to implement different logic
        returns Edit widget and related list or None
        """
        is_valid_form = True
        pages = get_page_args()
        page_sizes = get_page_size_args()
        orders = get_order_args()
        
        get_filter_args(self._filters, disallow_if_not_in_search=False)
        exclude_cols = self._filters.get_relation_cols()

        item = self.datamodel.get(pk, self._base_filters)
        if not item:
            abort(404)
        # convert pk to correct type, if pk is non string type.
        pk = self.datamodel.get_pk_value(item)

        if request.method == "POST":
            form = self.edit_form.refresh(request.form)
            # fill the form with the suppressed cols, generated from exclude_cols
            self._fill_form_exclude_cols(exclude_cols, form)
            # trick to pass unique validation
            form._id = pk
            if form.validate():
                self.process_form(form, False)
                try:
                    form.populate_obj(item)
                    self.pre_update(item)
                except Exception as e:
                    flash(str(e), "danger")
                else:
                    if self.datamodel.edit(item):
                        self.post_update(item)
                    flash(*self.datamodel.message)
                finally:
                    return None
            else:
                is_valid_form = False
        else:
            # Only force form refresh for select cascade events
            form = self.edit_form.refresh(obj=item)
            # Perform additional actions to pre-fill the edit form.
            self.prefill_form(form, pk)

        exclude_cols = exclude_cols or []
        widgets = {}
        widgets["edit"] = FormWidget(
            route_base=self.route_base,
            form=form,
            include_cols=self.form_columns,
            exclude_cols=exclude_cols,
            fieldsets=self.form_fieldsets,
        )
        if is_valid_form:
            self.update_redirect()
        return widgets