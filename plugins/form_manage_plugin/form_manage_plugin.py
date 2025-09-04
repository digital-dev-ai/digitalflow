from airflow.plugins_manager import AirflowPlugin
from flask import send_from_directory, abort, Blueprint
from plugins.form_manage_plugin.views.doc_class_view import DocClassManageView

external_static_path = "/opt/airflow/data"  # 외부 이미지 폴더 절대경로
external_static_bp = Blueprint('static', __name__)

@external_static_bp.route('/static/<path:filename>')
def serve_external_static(filename):
    try:
        return send_from_directory(external_static_path, filename)
    except FileNotFoundError:
        abort(404)

v_flask_blueprints = [
    external_static_bp
]
v_appbuilder_views = [
    {"name": "서식그룹 관리","category": "문서서식 관리","view": DocClassManageView()},
    #{"name": "서식 관리","category": "문서서식 관리","view": DocClassManageView()},
    # {"name": "영역 관리","category": "문서서식 관리","view": DocClassManageView()},
    # {"name": "블록 관리","category": "문서서식 관리","view": DocClassManageView()},
    # {"name": "교정사전 관리","category": "문서서식 관리","view": DocClassManageView()},
    # {"name": "조건별 교정사전 관리","category": "문서서식 관리","view": DocClassManageView()},
    # {"name": "데이터 조회","category": "문서서식 관리","view": DocClassManageView()}
]

# 플러그인 정의
class FormManagePlugin(AirflowPlugin):
    name = "form_manage_plugin"
    appbuilder_views = v_appbuilder_views
    flask_blueprints = v_flask_blueprints
    