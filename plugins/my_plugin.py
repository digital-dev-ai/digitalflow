from flask import Blueprint, request, render_template, redirect, url_for, jsonify
from airflow.plugins_manager import AirflowPlugin
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from flask_admin.base import MenuLink

    
# MariaDB 연결 URL 형식
#DATABASE_URI = "mysql+pymysql://user:password@host:port/database"
DATABASE_URI = "mysql+pymysql://digitalflow:digital10@192.168.10.18:3306/dococr"

engine = create_engine(DATABASE_URI, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


bp = Blueprint("my_plugin", __name__, url_prefix="/myplugin")

class MyPlugin(AirflowPlugin):
    name = "my_plugin"
    flask_blueprints = [bp]  # 위에서 정의한 Blueprint
    menu_links = [
        MenuLink(
            name="My Plugin",  # 메뉴에 표시될 이름
            category="Custom", # 사이드바 카테고리명
            url="/seo/list"  # 접근할 URL (Blueprint 경로 포함)
        )
    ]

@bp.route("/list", methods=["GET"])
def list_items():
    session = SessionLocal()
    try:
        items = session.execute("SELECT * FROM your_table").fetchall()
        return render_template("list.html", items=items)
    finally:
        session.close()

@bp.route("/add", methods=["POST"])
def add_item():
    session = SessionLocal()
    try:
        name = request.form.get("name")
        # 등록 쿼리 실행 예:
        session.execute("INSERT INTO your_table (name) VALUES (:name)", {"name": name})
        session.commit()
        return redirect(url_for("my_plugin.list_items"))
    except SQLAlchemyError as e:
        session.rollback()
        return f"Error: {str(e)}", 500
    finally:
        session.close()

@bp.route("/edit/<int:item_id>", methods=["POST"])
def edit_item(item_id):
    session = SessionLocal()
    try:
        new_name = request.form.get("name")
        session.execute("UPDATE your_table SET name=:name WHERE id=:id", {"name": new_name, "id": item_id})
        session.commit()
        return redirect(url_for("my_plugin.list_items"))
    except SQLAlchemyError as e:
        session.rollback()
        return f"Error: {str(e)}", 500
    finally:
        session.close()

@bp.route("/delete/<int:item_id>", methods=["POST"])
def delete_item(item_id):
    session = SessionLocal()
    try:
        session.execute("DELETE FROM your_table WHERE id=:id", {"id": item_id})
        session.commit()
        return redirect(url_for("my_plugin.list_items"))
    except SQLAlchemyError as e:
        session.rollback()
        return f"Error: {str(e)}", 500
    finally:
        session.close()
