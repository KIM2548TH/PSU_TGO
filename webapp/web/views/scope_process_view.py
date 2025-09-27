from flask import Blueprint, render_template, request
from flask_login import login_required
from ...models import Scope, Material, CampusAndDepartment
from datetime import datetime

module = Blueprint("scope_process", __name__, url_prefix="/scope-progress")

@module.route("/", methods=["GET"])
@login_required
def progress_dashboard():
    """
    หน้าแดชบอร์ดสำหรับติดตามความคืบหน้าการกรอกข้อมูล
    โดยจะแสดงข้อมูลแยกตามคณะ/หน่วยงาน ภายใต้ Campus และ Scope ที่เลือก
    """
    # --- 1. รับค่าจาก Query Parameters ---
    selected_year = request.args.get("year", default=datetime.now().year, type=int)
    selected_campus_id = request.args.get("campus_id")
    
    # รับค่า ghg_scope จาก query string
    try:
        selected_ghg_scope = request.args.get("ghg_scope", "all")
        if selected_ghg_scope != "all":
            selected_ghg_scope = int(selected_ghg_scope)
    except ValueError:
        selected_ghg_scope = "all"

    # --- 2. เตรียมข้อมูลสำหรับ Dropdown Filters ---
    # ดึง campus ทั้งหมด (ไม่ต้อง filter ด้วย campus__isnull=True)
    all_campuses = CampusAndDepartment.objects()

    # หากยังไม่มีการเลือก Campus ให้ใช้ Campus แรกเป็นค่าเริ่มต้น
    if not selected_campus_id and all_campuses:
        selected_campus_id = str(all_campuses.first().id)

    # ดึงชื่อ Campus ที่เลือก
    selected_campus_name = ""
    campus_obj = None
    if selected_campus_id:
        campus_obj = CampusAndDepartment.objects(id=selected_campus_id).first()
        if campus_obj:
            selected_campus_name = campus_obj.name.get("0", str(selected_campus_id))

    # --- 3. ดึงข้อมูลหลักตาม Filter ที่เลือก ---
    # ดึง Scope ทั้งหมดใน campus ที่เลือก
    if selected_ghg_scope == "all":
        scopes = Scope.objects(campus=selected_campus_id).order_by("ghg_scope", "ghg_sup_scope")
    else:
        scopes = Scope.objects(campus=selected_campus_id, ghg_scope=selected_ghg_scope).order_by("ghg_scope", "ghg_sup_scope")

    departments_data = []
    campus_total_sources = 0
    campus_completed = 0
    campus_in_progress = 0
    campus_not_started = 0
    campus_progress_sum = 0

    if campus_obj and campus_obj.departments:
        for dept_key, dept_name in campus_obj.departments.items():
            dept_scopes = scopes.filter(department=dept_key) if hasattr(scopes, "filter") else [s for s in scopes if s.department == dept_key]
            dept_total = len(dept_scopes)
            dept_completed = 0
            dept_in_progress = 0
            dept_not_started = 0
            dept_progress_sum = 0

            for scope in dept_scopes:
                num_head_table = len(scope.head_table)
                total_fields_required = num_head_table * 12 if num_head_table > 0 else 0
                materials_qs = Material.objects(
                    scope=scope.ghg_scope,
                    sub_scope=scope.ghg_sup_scope,
                    year=selected_year,
                    campus=selected_campus_id,
                    department=dept_key,
                )
                filled = materials_qs.filter(result__nin=[None, "", 0, "0"]).count()
                progress = (filled / total_fields_required) * 100 if total_fields_required > 0 else 0
                dept_progress_sum += progress

                if progress == 0:
                    dept_not_started += 1
                elif progress >= 100:
                    dept_completed += 1
                else:
                    dept_in_progress += 1

            avg_progress = dept_progress_sum / dept_total if dept_total > 0 else 0
            departments_data.append({
                "name": dept_name,
                "progress": round(avg_progress, 1),
                "total": dept_total,
                "in_progress": dept_in_progress,
                "not_started": dept_not_started,
                "completed": dept_completed,
            })

            campus_total_sources += dept_total
            campus_completed += dept_completed
            campus_in_progress += dept_in_progress
            campus_not_started += dept_not_started
            campus_progress_sum += avg_progress

    overall_progress = round(campus_progress_sum / len(departments_data), 1) if departments_data else 0
    total_sources = campus_total_sources
    completed = campus_completed
    in_progress = campus_in_progress
    not_started = campus_not_started

    # --- 6. ส่งข้อมูลไปยัง Template ---
    context = {
        "all_campuses": all_campuses,
        "selected_year": selected_year,
        "selected_campus_id": selected_campus_id,
        "selected_campus_name": selected_campus_name,
        "overall_progress": overall_progress,
        "total_sources": total_sources,
        "in_progress": in_progress,
        "not_started": not_started,
        "completed": completed,
        "departments_data": departments_data,
    }

    return render_template("scope-progress/scope-progress.html", **context)

