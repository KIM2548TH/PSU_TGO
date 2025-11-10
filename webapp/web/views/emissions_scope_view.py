from flask import Blueprint, render_template, redirect, url_for, request, jsonify, session
from flask_login import login_required, current_user
from ...models import FormAndFormula, Scope, Material, CampusAndDepartment
from datetime import datetime
from ..utils.acl import permissions_required_all
from flask import make_response
import json
import urllib.parse

module = Blueprint("emissions_scope", __name__, url_prefix="/emissions-scope")


@module.route("/", methods=["GET"])
@login_required
@permissions_required_all(["เข้าถึงหน้าข้อมูลการปล่อย"])
def emissions_scope():
    # รับปีที่เลือกจาก query parameter หรือใช้ปีปัจจุบันเป็นค่าเริ่มต้น
    selected_year = request.args.get("year", default=datetime.now().year, type=int)
    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(user.campus_id, user.department_key)
    # ดึงข้อมูล Scope ที่ตรงกับ campus และ department ของ current_user
    scopes = Scope.objects(
        campus=user.campus_id, department=user.department_key
    ).order_by("ghg_scope", "ghg_sup_scope")

    # ดึงปีทั้งหมดที่มีในฐานข้อมูล Material สำหรับ dropdown
    all_years = Material.objects().distinct("year")
    all_years = sorted([year for year in all_years if year is not None], reverse=True)

    # ถ้าไม่มีปีในฐานข้อมูล ให้เพิ่มปีปัจจุบัน
    if not all_years:
        all_years = [datetime.now().year]
    elif selected_year not in all_years:
        all_years.append(selected_year)
        all_years.sort(reverse=True)

    # จัดกลุ่ม Scope ตาม ghg_scope
    grouped_scopes = {}
    overall_progress = 0
    total_sources = len(scopes)
    completed = 0
    in_progress = 0
    not_started = 0

    for scope in scopes:
        main_scope = f"Scope {scope.ghg_scope}"
        if main_scope not in grouped_scopes:
            grouped_scopes[main_scope] = []

        # คำนวณ Progress สำหรับ Scope นี้ (เฉพาะปีที่เลือก)
        progress = calculate_scope_progress(scope, selected_year)

        # กำหนดสถานะตาม Progress
        if progress == 100:
            status = "Completed"
            completed += 1
        elif progress > 0:
            status = "In progress"
            in_progress += 1
        else:
            status = "Not started"
            not_started += 1

        # เพิ่ม Progress รวม
        overall_progress += progress

        # เพิ่ม progress และ status เข้าไปใน scope object
        scope.progress = round(progress, 1)
        scope.status = status

        # ส่ง scope object ทั้งหมดไปเลย
        grouped_scopes[main_scope].append(scope)

    # คำนวณ Overall Progress
    overall_progress = (
        round(overall_progress / total_sources, 1) if total_sources > 0 else 0
    )

    return render_template(
        "/emissions-scope/emissions-scope.html",
        user=user,
        mockup_data={
            "overall_progress": overall_progress,
            "total_sources": total_sources,
            "in_progress": in_progress,
            "not_started": not_started,
            "completed": completed,
            "scopes": grouped_scopes,
            "selected_year": selected_year,
            "all_years": all_years,
        },
    )


def calculate_scope_progress(scope, selected_year):
    """
    คำนวณ Progress:
    - นับเฉพาะ Material ที่อยู่ใน scope นี้เท่านั้น
    - นับ result ที่ไม่เป็น None หรือ "" (รวม 0 ด้วย)
    - ถ้า result = 0 ถือว่ากรอกแล้ว
    """
    num_head_table = len(scope.head_table)
    if num_head_table == 0:
        return 0

    total_fields_required = num_head_table * 12
    if total_fields_required == 0:
        return 0

    materials_qs = Material.objects(
        scope=scope.ghg_scope,
        sub_scope=scope.ghg_sup_scope,
        year=selected_year,
        campus=current_user.campus_id,
        department=current_user.department_key,
    )

    # นับเฉพาะ result ที่มีค่า (รวม 0 ด้วย) - ไม่นับ None และ "" เท่านั้น
    filled = materials_qs.filter(result__nin=[None, ""]).count()

    progress = (filled / total_fields_required) * 100
    return min(progress, 100)




@module.route("/get-latest-sub-scope", methods=["POST"])
@login_required
@permissions_required_all(["แก้ไขข้อมูลการปล่อย"])
def get_latest_sub_scope():
    ghg_scope = request.json.get("ghg_scope")  # รับข้อมูลจาก JSON
    if not ghg_scope or not ghg_scope.isdigit():
        return jsonify({"latest_sub_scope": 1})  # ถ้า Scope หลักว่างหรือไม่ใช่ตัวเลข ให้เริ่มที่ 1

    ghg_scope = int(ghg_scope)

    # แก้ไข: เพิ่มการกรองตาม campus และ department ของ current_user
    latest_sub_scope = (
        Scope.objects(
            ghg_scope=ghg_scope,
            campus=current_user.campus,
            department=current_user.department,
        )
        .order_by("-ghg_sup_scope")
        .first()
    )

    latest_sub_scope = latest_sub_scope.ghg_sup_scope + 1 if latest_sub_scope else 1
    return jsonify({"latest_sub_scope": latest_sub_scope})


@module.route("/edit/<int:ghg_scope>/<int:ghg_sup_scope>", methods=["GET", "POST"])
@login_required
@permissions_required_all(["แก้ไขข้อมูลการปล่อย"])
def edit_scope(ghg_scope, ghg_sup_scope):
    # ค้นหา Scope ที่ต้องการแก้ไขตาม campus และ department ของ current_user
    scope = Scope.objects(
        ghg_scope=ghg_scope,
        ghg_sup_scope=ghg_sup_scope,
        campus=current_user.campus_id,
        department=current_user.department_key,
    ).first()

    if not scope:
        return render_template(
            "/emissions-scope/edit-scope-error.html",
            error="ไม่พบ Scope ที่ต้องการแก้ไข หรือคุณไม่มีสิทธิ์เข้าถึง",
        )

    if request.method == "POST":
        ghg_name = request.form.get("ghg_name")  # รับจาก hidden input
        ghg_desc = request.form.get("ghg_desc")  # รับจาก hidden input
        head_table = request.form.getlist("head_table")

        # อัปเดตข้อมูล (ไม่ต้องตรวจสอบ name และ desc เพราะเป็น hidden input)
        scope.head_table = head_table if head_table else []
        scope.save()

        # ใช้ toast notification แทน popup

        
        response = make_response('')
        encoded_message = urllib.parse.quote("แก้ไข Scope สำเร็จ!")
        
        trigger_data = {
            "closeModal": True,
            "showSuccess": encoded_message,
            "refreshPage": True
        }
        response.headers['HX-Trigger'] = json.dumps(trigger_data)
        
        return response

    # กรณี GET: แสดงฟอร์มแก้ไข
    # ดึง material_names จาก FormAndFormula ที่ตรงกับ scope และ sub_scope
    materials = FormAndFormula.objects(
        ghg_scope=ghg_scope,
        ghg_sup_scope=ghg_sup_scope  # แก้จาก ghg_sub_scope เป็น ghg_sup_scope
    ).distinct("material_name")
    
    print(materials)
    
    material_names = sorted([name for name in materials if name])

    # ดึงชื่อจริงของ campus และ department
    campus_name = ""
    department_name = ""
    
    try:
        from ...models.campus_and_department_model import CampusAndDepartment
        campus_doc = CampusAndDepartment.objects(id=current_user.campus_id).first()
        if campus_doc:
            campus_name = campus_doc.name.get("0", "")
            department_name = campus_doc.departments.get(current_user.department_key, "")
    except Exception as e:
        print(f"Error getting campus/department names: {e}")
        campus_name = scope.campus
        department_name = scope.department

    return render_template(
        "/emissions-scope/edit-scope.html", 
        scope=scope, 
        material_names=material_names,
        campus_name=campus_name,
        department_name=department_name
    )




@module.route("/scope-description/<int:ghg_scope>/<int:ghg_sup_scope>", methods=["GET"])
@login_required
def scope_description(ghg_scope, ghg_sup_scope):
    """แสดง popup description ของ Scope"""
    try:
        # ค้นหา Scope ที่ต้องการ
        scope = Scope.objects(
            ghg_scope=ghg_scope,
            ghg_sup_scope=ghg_sup_scope,
            campus=current_user.campus_id,
            department=current_user.department_key,
        ).first()

        if not scope:
            return render_template(
                "/emissions-scope/partials/scope-description-modal.html",
                error="ไม่พบข้อมูล Scope ที่ต้องการ",
            )

        # ดึงชื่อจริงของ campus และ department
        campus_name = ""
        department_name = ""
        
        try:
            from ...models.campus_and_department_model import CampusAndDepartment
            campus_doc = CampusAndDepartment.objects(id=current_user.campus_id).first()
            if campus_doc:
                campus_name = campus_doc.name.get("0", "")
                department_name = campus_doc.departments.get(current_user.department_key, "")
        except Exception as e:
            print(f"Error getting campus/department names: {e}")
            campus_name = scope.campus
            department_name = scope.department

        return render_template(
            "/emissions-scope/partials/scope-description-modal.html", 
            scope=scope,
            campus_name=campus_name,
            department_name=department_name
        )

    except Exception as e:
        return render_template(
            "/emissions-scope/partials/scope-description-modal.html",
            error=f"เกิดข้อผิดพลาด: {str(e)}",
        )
