from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from ...models import FormAndFormula, Scope, Material, CampusAndDepartment
from datetime import datetime
from ..utils.acl import permissions_required_all

module = Blueprint("emissions_scope", __name__, url_prefix="/emissions-scope")


@module.route("/", methods=["GET"])
@login_required
@permissions_required_all(["เข้าถึงข้อมูลการปล่อย"])
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
    คำนวณ Progress ของ Scope สำหรับปีที่เลือก
    Progress = (จำนวนช่องที่กรอกแล้ว / (head_table × 12)) × 100
    """
    # จำนวน head_table
    num_head_table = len(scope.head_table)

    if num_head_table == 0:
        return 0  # ถ้าไม่มี head_table ให้ progress = 0

    # จำนวนช่องทั้งหมดที่ต้องกรอก = head_table × 12 เดือน (เฉพาะปีที่เลือก)
    total_fields_required = num_head_table * 12

    if total_fields_required == 0:
        return 0

    # ดึง Material ที่เกี่ยวข้องกับ Scope นี้ในปีที่เลือก
    materials = Material.objects(
        scope=scope.ghg_scope,
        sub_scope=scope.ghg_sup_scope,
        year=selected_year,
        campus=current_user.campus_id,
        department=current_user.department_key,
    )

    # นับจำนวนช่องที่กรอกข้อมูลแล้ว
    filled_fields = len(materials)

    # คำนวณ Progress
    progress = (filled_fields / total_fields_required) * 100

    # จำกัดไม่ให้เกิน 100%
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

        return render_template("/success/success.html", success="แก้ไข Scope สำเร็จ!")

    # กรณี GET: แสดงฟอร์มแก้ไข
    # ดึง material_names จาก FormAndFormula ที่ตรงกับ scope และ sub_scope
    materials = FormAndFormula.objects(
        ghg_scope=ghg_scope,
        ghg_sup_scope=ghg_sup_scope  # แก้จาก ghg_sub_scope เป็น ghg_sup_scope
    ).distinct("material_name")
    
    print(materials)
    
    material_names = sorted([name for name in materials if name])

    return render_template(
        "/emissions-scope/edit-scope.html", scope=scope, material_names=material_names
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

        return render_template(
            "/emissions-scope/partials/scope-description-modal.html", scope=scope
        )

    except Exception as e:
        return render_template(
            "/emissions-scope/partials/scope-description-modal.html",
            error=f"เกิดข้อผิดพลาด: {str(e)}",
        )
