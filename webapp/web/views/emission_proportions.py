import datetime
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    jsonify,
    make_response,
)
from flask_login import login_required, logout_user, current_user
from ..forms.user_form import LoginForm, RegisterForm, EditUserForm, EditprofileForm
from ...services.user_service import UserService
from ...models import User, Role, Permission, Scope, FormAndFormula
from ...models.materail_model import Material, QuantityType
from ..forms.material_form import MaterialForm
from ...models.file_model import ReferenceDocument, UploadedFile
from urllib.parse import quote
from ...models.scope_model import Scope
from ...models.campus_and_department_model import CampusAndDepartment
from ...models.form_and_formula_model import FormAndFormula
from ..utils.acl import permissions_required_all
module = Blueprint("proportions", __name__, url_prefix="/proportions")


@module.route("/", methods=["GET"])
@login_required
@permissions_required_all(["เข้าถึงข้อมูลสัดส่วนการปล่อย"])
def emission_proportions():
    user_campus = current_user.campus_id
    user_department = current_user.department_key

    current_year = datetime.datetime.now().year
    query_filter = {
        "campus": user_campus,
        "result2__ne": None,
        "result2__exists": True,
        "year": current_year,  # เพิ่มเงื่อนไขปีปัจจุบัน
    }
    if user_department and user_department.strip():
        query_filter["department"] = user_department

    materials = Material.objects(**query_filter).order_by("scope", "sub_scope", "name")

    # Group by scope/sub_scope
    scopes = {}
    grand_total = 0
    scope_totals = {}
    scope_material_counts = {}

    for m in materials:
        scope = m.scope
        sub_scope = m.sub_scope
        result2 = float(m.result2) if m.result2 else 0.0

        if scope not in scopes:
            scopes[scope] = {}
            scope_totals[scope] = 0
            scope_material_counts[scope] = 0
        if sub_scope not in scopes[scope]:
            scopes[scope][sub_scope] = []

        scopes[scope][sub_scope].append(m)
        scope_totals[scope] += result2
        scope_material_counts[scope] += 1
        grand_total += result2

    # Prepare data for template
    scope_data = []
    for scope in sorted(scopes.keys()):
        sub_scopes = []
        for sub_scope in sorted(scopes[scope].keys()):
            # รวม material ที่ชื่อเดียวกัน
            material_dict = {}
            for mat in scopes[scope][sub_scope]:
                result2 = float(mat.result2) if mat.result2 else 0.0

                # ดึงชื่อ department
                department_name = CampusAndDepartment.get_department_name(
                    mat.campus, mat.department
                )

                # ดึงชื่อฟอร์มและสูตร
                form_name = ""
                if mat.form_and_formula:
                    form_obj = FormAndFormula.objects(id=mat.form_and_formula).first()
                    form_name = (
                        form_obj.desc_form if form_obj else str(mat.form_and_formula)
                    )

                key = mat.name  # รวมตามชื่อ material
                if key not in material_dict:
                    material_dict[key] = {
                        "name": mat.name,
                        "form_and_formula": form_name,
                        "year": mat.year,
                        "department": department_name,
                        "result2": 0.0,
                    }
                material_dict[key]["result2"] += result2

            # สร้าง materials_list จาก dict
            materials_list = []
            for item in material_dict.values():
                percent_scope1 = (
                    (item["result2"] / scope_totals.get(1, 1) * 100)
                    if scope_totals.get(1, 0) > 0
                    else 0
                )
                percent_scope1_2 = (
                    (
                        item["result2"]
                        / (scope_totals.get(1, 0) + scope_totals.get(2, 0))
                        * 100
                    )
                    if (scope_totals.get(1, 0) + scope_totals.get(2, 0)) > 0
                    else 0
                )
                percent_scope1_2_3 = (
                    (item["result2"] / grand_total * 100) if grand_total > 0 else 0
                )
                item.update(
                    {
                        "percent_scope1": percent_scope1,
                        "percent_scope1_2": percent_scope1_2,
                        "percent_scope1_2_3": percent_scope1_2_3,
                    }
                )
                materials_list.append(item)
            sub_scope_total = sum(
                float(mat.result2) if mat.result2 else 0.0
                for mat in scopes[scope][sub_scope]
            )
            # ดึงชื่อ ghg_name จาก Scope model
            scope_obj = Scope.objects(
                ghg_scope=scope,
                ghg_sup_scope=sub_scope,
                campus=user_campus,
                department=user_department,
            ).first()
            ghg_name = scope_obj.ghg_name if scope_obj else f"{scope}.{sub_scope}"

            sub_scope_percent_scope1 = (
                (sub_scope_total / scope_totals.get(1, 1) * 100)
                if scope_totals.get(1, 0) > 0
                else 0
            )
            sub_scope_percent_scope1_2 = (
                (
                    sub_scope_total
                    / (scope_totals.get(1, 0) + scope_totals.get(2, 0))
                    * 100
                )
                if (scope_totals.get(1, 0) + scope_totals.get(2, 0)) > 0
                else 0
            )
            sub_scope_percent_scope1_2_3 = (
                (sub_scope_total / grand_total * 100) if grand_total > 0 else 0
            )
            sub_scopes.append(
                {
                    "sub_scope": sub_scope,
                    "ghg_name": ghg_name,  # เพิ่ม ghg_name
                    "materials": materials_list,
                    "sub_scope_total": sub_scope_total,
                    "sub_scope_percent_scope1": sub_scope_percent_scope1,
                    "sub_scope_percent_scope1_2": sub_scope_percent_scope1_2,
                    "sub_scope_percent_scope1_2_3": sub_scope_percent_scope1_2_3,
                }
            )
        scope_data.append(
            {
                "scope": scope,
                "scope_total": scope_totals[scope],
                "material_count": scope_material_counts[scope],
                "scope_percentage": (
                    (scope_totals[scope] / grand_total * 100) if grand_total > 0 else 0
                ),
                "sub_scopes": sub_scopes,
            }
        )

    return render_template(
        "emission-proportions/emission-proportions.html",
        scope_data=scope_data,
        grand_total=grand_total,
        scope_totals=scope_totals,
    )


@module.route("/data", methods=["GET"])
@login_required
def emission_proportions_data():
    """
    Get emission proportions data based on current user's campus and department
    """
    try:
        # ดึงข้อมูล user ปัจจุบัน
        user_campus = current_user.campus_id
        user_department = current_user.department_key

        # Query materials
        query_filter = {
            "campus": user_campus,
            "result2__ne": None,
            "result2__exists": True,
        }

        if user_department and user_department.strip():
            query_filter["department"] = user_department

        materials = Material.objects(**query_filter).order_by(
            "scope", "sub_scope", "name"
        )

        # จัดกลุ่มข้อมูลตาม scope และ sub_scope
        scope_data = {}

        for material in materials:
            scope_key = material.scope
            sub_scope_key = material.sub_scope

            # สร้าง structure ถ้ายังไม่มี
            if scope_key not in scope_data:
                scope_data[scope_key] = {"scope": scope_key, "sub_scopes": {}}

            if sub_scope_key not in scope_data[scope_key]["sub_scopes"]:
                scope_data[scope_key]["sub_scopes"][sub_scope_key] = {
                    "sub_scope": sub_scope_key,
                    "materials": [],
                }

            # เพิ่ม material
            material_data = {
                "id": str(material.id),
                "name": material.name,
                "result2": float(material.result2) if material.result2 else 0.0,
                "year": material.year,
                "month": material.month,
                "day": material.day,
                "department": material.department,
                "campus": material.campus,
                "form_and_formula": material.form_and_formula,
                "scope": material.scope,
                "sub_scope": material.sub_scope,
            }

            scope_data[scope_key]["sub_scopes"][sub_scope_key]["materials"].append(
                material_data
            )

        # แปลง sub_scopes จาก dict เป็น list
        final_data = []
        for scope_key in sorted(scope_data.keys()):
            scope_item = scope_data[scope_key]
            scope_item["sub_scopes"] = [
                scope_item["sub_scopes"][sub_scope_key]
                for sub_scope_key in sorted(scope_item["sub_scopes"].keys())
            ]
            final_data.append(scope_item)

        return jsonify(
            {
                "status": "success",
                "data": final_data,
                "user_info": {"campus": user_campus, "department": user_department},
            }
        )

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@module.route("/summary", methods=["GET"])
@login_required
def emission_proportions_summary():
    """
    Get summary statistics of emission proportions
    """
    try:
        user_campus = current_user.campus_id
        user_department = current_user.department_key

        # Query filter
        query_filter = {
            "campus": user_campus,
            "result2__ne": None,
            "result2__exists": True,
        }

        if user_department and user_department.strip():
            query_filter["department"] = user_department

        materials = Material.objects(**query_filter)

        # คำนวณสถิติ
        total_materials = materials.count()
        total_result2 = sum(
            float(material.result2)
            for material in materials
            if material.result2 is not None
        )

        # นับจำนวนตาม scope
        scope_count = {}
        scope_result2_sum = {}

        for material in materials:
            scope = material.scope
            if scope not in scope_count:
                scope_count[scope] = 0
                scope_result2_sum[scope] = 0

            scope_count[scope] += 1
            if material.result2 is not None:
                scope_result2_sum[scope] += float(material.result2)

        # สร้าง summary ตาม scope
        scope_summary = []
        for scope in sorted(scope_count.keys()):
            scope_summary.append(
                {
                    "scope": scope,
                    "material_count": scope_count[scope],
                    "total_result2": scope_result2_sum[scope],
                    "percentage": (
                        (scope_result2_sum[scope] / total_result2 * 100)
                        if total_result2 > 0
                        else 0
                    ),
                }
            )

        return jsonify(
            {
                "status": "success",
                "summary": {
                    "total_materials": total_materials,
                    "total_result2": total_result2,
                    "scope_breakdown": scope_summary,
                },
            }
        )

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
