from airflow.plugins_manager import AirflowPlugin
from flask_appbuilder import BaseView as AppBuilderBaseView, expose, has_access
from flask import Blueprint

bp = Blueprint(
    "my_plugin", __name__,
    template_folder="templates/my_plugin"
)

class MyView(AppBuilderBaseView):
    @expose("/upload")
    @has_access
    def upload(self):
        return self.render_template("my_plugin/upload.html")

v_appbuilder_view = MyView()

v_appbuilder_package = {
    "name": "My View",
    "category": "My Plugin",
    "view": v_appbuilder_view
}

from airflow.plugins_manager import AirflowPlugin
from flask_appbuilder import BaseView as AppBuilderBaseView, expose, has_access
from flask import Blueprint

bp = Blueprint(
    "my_plugin", __name__,
    template_folder="templates/my_plugin"
)

class MyView(AppBuilderBaseView):
    default_view = "upload"
    @expose("/upload")
    @has_access
    def upload(self):
        return self.render_template("my_plugin/upload.html")

v_appbuilder_view = MyView()

v_appbuilder_package = {
    "name": "My View",
    "category": "My Plugin",
    "view": v_appbuilder_view
}
class MyPlugin(AirflowPlugin):
    name = "my_plugin"
    appbuilder_views = [v_appbuilder_package]
    flask_blueprints = [bp]
