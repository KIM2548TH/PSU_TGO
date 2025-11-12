import datetime
import io
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    jsonify,
    make_response,
    send_file,
)
from flask_login import login_required, logout_user, current_user
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
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
import json
import urllib.parse
from reportlab.pdfbase.pdfmetrics import getFont

module = Blueprint("proportions", __name__, url_prefix="/proportions")


def create_htmx_response(template_path, template_vars=None, success_message=None, error_message=None, warning_message=None):
    """Helper function สำหรับสร้าง HTMX response พร้อม toast notification"""
    if template_vars is None:
        template_vars = {}
    
    response = make_response(render_template(template_path, **template_vars))
    
    trigger_data = {}
    if success_message:
        trigger_data["showSuccess"] = urllib.parse.quote(success_message)
    if error_message:
        trigger_data["showError"] = urllib.parse.quote(error_message)
    if warning_message:
        trigger_data["showWarning"] = urllib.parse.quote(warning_message)
    
    if trigger_data:
        response.headers['HX-Trigger'] = json.dumps(trigger_data)
    
    return response


@module.route("/", methods=["GET"])
@login_required
@permissions_required_all(["เข้าถึงหน้าสัดส่วนการปล่อย"])
def emission_proportions():
    user_campus = current_user.campus_id
    user_department = current_user.department_key

    current_year = datetime.datetime.now().year

    # ดึงปีทั้งหมดที่มีข้อมูล
    base_year_filter = {
        "campus": user_campus,
        "result2__ne": None,
        "result2__exists": True,
    }
    if user_department and user_department.strip():
        base_year_filter["department"] = user_department

    years = Material.objects(**base_year_filter).distinct("year") or []
    years = sorted([y for y in years if isinstance(y, int)], reverse=True)
    selected_year = request.args.get("year", type=int)
    if not selected_year:
        selected_year = years[0] if years else current_year
    if years and selected_year not in years:
        selected_year = years[0]

    # ใช้ปีที่เลือกเป็นตัวกรอง
    query_filter = dict(base_year_filter)
    query_filter["year"] = selected_year

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

    # NEW: ดึงชื่อ Campus / Department ที่อ่านง่าย
    campus_name = CampusAndDepartment.get_campus_name(user_campus) if hasattr(CampusAndDepartment, "get_campus_name") else user_campus
    department_name = CampusAndDepartment.get_department_name(user_campus, user_department) if user_department else "-"

    # NEW: สรุปข้อมูลเบื้องต้น
    total_materials = len(materials)
    total_scopes = len(scope_totals.keys())
    scope_coverage = [
        {
            "scope": s,
            "total": scope_totals[s],
            "percent": (scope_totals[s] / grand_total * 100) if grand_total > 0 else 0,
        }
        for s in sorted(scope_totals.keys())
    ]

    page_meta = {
        "title": f"สัดส่วนการปล่อยก๊าซเรือนกระจก ปี {selected_year}",
        "description": "สรุปสัดส่วนการปล่อยตาม Scope / Sub-Scope และสัดส่วนต่อภาพรวมทั้งหมด",
        "campus": campus_name,
        "department": department_name,
        "selected_year": selected_year,
        "total_materials": total_materials,
        "total_scopes": total_scopes,
        "grand_total": grand_total,
        "scope_coverage": scope_coverage,
    }

    return render_template(
        "emission-proportions/emission-proportions.html",
        scope_data=scope_data,
        grand_total=grand_total,
        scope_totals=scope_totals,
        years=years,
        selected_year=selected_year,
        page_meta=page_meta,  # NEW
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


@module.route("/download-pdf", methods=["GET"])
@login_required
@permissions_required_all(["ดาวน์โหลดรายงานสัดส่วนการปล่อย"])
def download_pdf_modal():
    """
    Show PDF download modal
    """
    selected_year = request.args.get("year", datetime.datetime.now().year, type=int)
    return render_template("emission-proportions/partials/download-pdf-modal.html", 
                         selected_year=selected_year)


@module.route("/preview-pdf", methods=["GET"])
@login_required
@permissions_required_all(["พรีวิวรายงานสัดส่วนการปล่อย"])
def preview_pdf_modal():
    """
    Show PDF preview modal
    """
    selected_year = request.args.get("year", datetime.datetime.now().year, type=int)
    return render_template("emission-proportions/partials/preview-pdf-modal.html", 
                         selected_year=selected_year)


@module.route("/download-pdf", methods=["POST"])
@login_required
@permissions_required_all(["ดาวน์โหลดรายงานสัดส่วนการปล่อย"])
def download_pdf():
    """
    Generate and download PDF report of emission proportions
    """
    try:
        # รับข้อมูลจากฟอร์ม
        report_title = request.form.get("report_title", "รายงานสัดส่วนการปล่อยก๊าซเรือนกระจก")
        notes = request.form.get("notes", "")
        pdf_format = request.form.get("pdf_format", "detailed")
        selected_year = int(request.form.get("year", datetime.datetime.now().year))
        is_htmx = request.form.get("htmx_request") == "1"
        
        # ดึงข้อมูลเดียวกับหน้าหลัก
        user_campus = current_user.campus_id
        user_department = current_user.department_key
        
        # ดึงข้อมูล materials
        base_year_filter = {
            "campus": user_campus,
            "result2__ne": None,
            "result2__exists": True,
            "year": selected_year,
        }
        if user_department and user_department.strip():
            base_year_filter["department"] = user_department

        materials = Material.objects(**base_year_filter).order_by("scope", "sub_scope", "name")

        # Group by scope/sub_scope (เหมือนกับหน้าหลัก)
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

        # Prepare data for template (เหมือนกับหน้าหลัก)
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
                        "ghg_name": ghg_name,
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

        # สร้าง page_meta
        campus_name = CampusAndDepartment.get_campus_name(user_campus) if hasattr(CampusAndDepartment, "get_campus_name") else user_campus
        department_name = CampusAndDepartment.get_department_name(user_campus, user_department) if user_department else "-"
        
        total_materials = len(materials)
        total_scopes = len(scope_totals.keys())
        scope_coverage = [
            {
                "scope": s,
                "total": scope_totals[s],
                "percent": (scope_totals[s] / grand_total * 100) if grand_total > 0 else 0,
            }
            for s in sorted(scope_totals.keys())
        ]

        page_meta = {
            "title": f"สัดส่วนการปล่อยก๊าซเรือนกระจก ปี {selected_year}",
            "description": "สรุปสัดส่วนการปล่อยตาม Scope / Sub-Scope และสัดส่วนต่อภาพรวมทั้งหมด",
            "campus": campus_name,
            "department": department_name,
            "selected_year": selected_year,
            "total_materials": total_materials,
            "total_scopes": total_scopes,
            "grand_total": grand_total,
            "scope_coverage": scope_coverage,
        }

        # สร้าง PDF ด้วย ReportLab (เหมือนหน้าเว็บ)
        generated_date = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        
        # ลงทะเบียน Thai font สำหรับภาษาไทย - รองรับทั้ง Windows และ Linux
        try:
            thai_font_path = None
            
            # ตรวจสอบ OS และกำหนด possible fonts ตาม platform
            import platform
            system = platform.system().lower()
            
            if system == 'windows':
                # Windows fonts
                possible_fonts = [
                    'C:/Windows/Fonts/tahoma.ttf',
                    'C:/Windows/Fonts/tahomabd.ttf', 
                    'C:/Windows/Fonts/arial.ttf',
                    'C:/Windows/Fonts/cordia.ttf',
                    'C:/Windows/Fonts/cordiau.ttf'
                ]
            else:
                # Linux/Unix fonts (Ubuntu, CentOS, etc.)
                possible_fonts = [
                    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                    '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
                    '/usr/share/fonts/TTF/DejaVuSans.ttf',
                    '/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf',
                    '/usr/share/fonts/truetype/thai/Garuda.ttf',
                    '/usr/share/fonts/truetype/thai/Kinnari.ttf',
                    '/usr/share/fonts/truetype/thai/Laksaman.ttf',
                    '/usr/share/fonts/truetype/thai/Norasi.ttf',
                    '/usr/share/fonts/truetype/thai/Purisa.ttf',
                    '/usr/share/fonts/truetype/thai/Sawasdee.ttf',
                    '/usr/share/fonts/truetype/thai/TlwgMono.ttf',
                    '/usr/share/fonts/truetype/thai/TlwgTypewriter.ttf',
                    '/usr/share/fonts/truetype/thai/Umpush.ttf',
                    '/usr/share/fonts/truetype/thai/Waree.ttf'
                ]
            
            # หา font ที่มีอยู่
            for font_path in possible_fonts:
                if os.path.exists(font_path):
                    thai_font_path = font_path
                    break
            
            if thai_font_path:
                pdfmetrics.registerFont(TTFont('ThaiFont', thai_font_path))
                
                # ลงทะเบียน bold font ตาม platform
                bold_font_path = None
                if system == 'windows':
                    bold_font_path = thai_font_path.replace('.ttf', 'bd.ttf')
                    if not os.path.exists(bold_font_path):
                        bold_font_path = thai_font_path.replace('.ttf', 'b.ttf')
                else:
                    # Linux bold fonts
                    bold_alternatives = [
                        thai_font_path.replace('.ttf', '-Bold.ttf'),
                        thai_font_path.replace('Regular', 'Bold'),
                        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
                        '/usr/share/fonts/TTF/DejaVuSans-Bold.ttf'
                    ]
                    for bold_path in bold_alternatives:
                        if os.path.exists(bold_path):
                            bold_font_path = bold_path
                            break
                
                if bold_font_path and os.path.exists(bold_font_path):
                    pdfmetrics.registerFont(TTFont('ThaiFontBold', bold_font_path))
                else:
                    # ใช้ font เดียวกันสำหรับ bold
                    pdfmetrics.registerFont(TTFont('ThaiFontBold', thai_font_path))
                
                thai_font_name = 'ThaiFont'
                thai_font_bold = 'ThaiFontBold'
                print(f"✓ ใช้ Thai font: {thai_font_path}")
            else:
                # ถ้าไม่เจอ font ไทย ใช้ DejaVu (ซึ่งรองรับ Unicode ได้ดีกว่า Helvetica)
                print("⚠ ไม่พบ Thai font ใช้ Helvetica แทน")
                thai_font_name = 'Helvetica'
                thai_font_bold = 'Helvetica-Bold'
        except Exception as e:
            # Fallback ถ้ามีปัญหา
            print(f"❌ Font loading error: {str(e)}")
            thai_font_name = 'Helvetica'
            thai_font_bold = 'Helvetica-Bold'
        
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
        styles = getSampleStyleSheet()
        
        # กำหนด style ให้เหมือนหน้าเว็บ (ใช้ Thai font)
        title_style = ParagraphStyle(
            'WebTitle',
            parent=styles['Heading1'],
            fontSize=20,  # ลดขนาดฟอนต์จาก 24 เป็น 20 เพื่อให้พอดีในบรรทัดเดียว
            spaceAfter=10,
            textColor=colors.Color(30/255, 64/255, 175/255),  # text-blue-800
            alignment=1,
            fontName=thai_font_bold,
            keepWithNext=True,  # ป้องกันการแบ่งบรรทัด
            wordWrap='LTR'  # จัดคำจากซ้ายไปขวา
        )
        
        meta_style = ParagraphStyle(
            'WebMeta',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=20,
            textColor=colors.grey,
            alignment=1,
            fontName=thai_font_name
        )
        
        scope_title_style = ParagraphStyle(
            'ScopeTitle',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=8,
            fontName=thai_font_bold
        )
        
        sub_scope_style = ParagraphStyle(
            'SubScope',
            parent=styles['Heading3'],
            fontSize=12,
            spaceAfter=5,
            fontName=thai_font_bold
        )
        
        normal_style = ParagraphStyle(
            'WebNormal',
            parent=styles['Normal'],
            fontSize=9,
            spaceAfter=6,
            fontName=thai_font_name
        )

        # สร้างเนื้อหา PDF ตามรูปแบบหน้าเว็บ
        story = []
        
        # Header Section (ปรับให้เป็นระเบียบมากขึ้น)
        # Title - แก้ไขให้เป็นบรรทัดเดียว
        title_text = page_meta['title'].replace('\n', ' ').replace('  ', ' ')  # แทนที่ \n ด้วยช่องว่าง
        story.append(Paragraph(title_text, title_style))
        story.append(Spacer(1, 10))
        
        # Meta Information Table - แบ่งเป็น 2 ข้าง
        meta_data = [
            # University name row - span ทั้งหมด
            ['มหาวิทยาลัยสงขลานครินทร์', '', '', ''],
            # แบ่งเป็น 2 ข้าง: ซ้าย (Campus, Department) | ขวา (Year, สร้างรายงานเมื่อ)
            ['Campus:', page_meta['campus'], 'Year:', str(page_meta['selected_year'])],
            ['Department:', page_meta['department'], 'สร้างรายงานเมื่อ:', generated_date]
        ]
        
        meta_table = Table(meta_data, colWidths=[1.5*inch, 2.0*inch, 1.5*inch, 2.5*inch])
        meta_table.setStyle(TableStyle([
            # University name row - span across all columns
            ('SPAN', (0, 0), (-1, 0)),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), thai_font_bold),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.Color(75/255, 85/255, 99/255)),  # text-gray-600
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            
            # Data rows - ข้างซ้าย (Campus, Department)
            ('FONTNAME', (0, 1), (1, -1), thai_font_name),
            ('FONTSIZE', (0, 1), (1, -1), 10),
            ('TEXTCOLOR', (0, 1), (0, -1), colors.Color(107/255, 114/255, 128/255)),  # Labels gray-500
            ('TEXTCOLOR', (1, 1), (1, -1), colors.Color(55/255, 65/255, 81/255)),   # Values gray-700
            ('ALIGN', (0, 1), (0, -1), 'RIGHT'),    # Labels align right
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),     # Values align left
            ('FONTNAME', (1, 1), (1, -1), thai_font_bold),  # Values bold
            
            # Data rows - ข้างขวา (Year, สร้างรายงานเมื่อ)
            ('FONTNAME', (2, 1), (3, -1), thai_font_name),
            ('FONTSIZE', (2, 1), (3, -1), 10),
            ('TEXTCOLOR', (2, 1), (2, -1), colors.Color(107/255, 114/255, 128/255)),  # Labels gray-500
            ('TEXTCOLOR', (3, 1), (3, -1), colors.Color(55/255, 65/255, 81/255)),   # Values gray-700
            ('ALIGN', (2, 1), (2, -1), 'RIGHT'),    # Labels align right
            ('ALIGN', (3, 1), (3, -1), 'LEFT'),     # Values align left
            ('FONTNAME', (3, 1), (3, -1), thai_font_bold),  # Values bold
            
            # Padding และ alignment
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('LEFTPADDING', (0, 1), (-1, -1), 8),
            ('RIGHTPADDING', (0, 1), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # เส้นแบ่งกลาง (เอาออกแล้ว)
            # ('LINEAFTER', (1, 1), (1, -1), 0.5, colors.Color(229/255, 231/255, 235/255)),  # เส้นแบ่งข้างซ้ายกับขวา
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 20))
        
        # Detailed Data - เหมือนหน้าเว็บ (แสดงรายละเอียดทั้งหมดเสมอ)
        for scope in scope_data:
            # กำหนดสีตาม Scope เหมือนหน้าเว็บ
            scope_colors = {
                1: colors.Color(124/255, 58/255, 237/255),    # purple
                2: colors.Color(5/255, 150/255, 105/255),     # green  
                3: colors.Color(37/255, 99/255, 235/255)      # blue
            }
            scope_color = scope_colors.get(scope['scope'], colors.blue)
            
            # Scope Header (เหมือนหน้าเว็บ)
            scope_title = f"Scope {scope['scope']} - "
            if scope['scope'] == 1:
                scope_title += "การปล่อยมลพิษทางตรง"
            elif scope['scope'] == 2:
                scope_title += "การปล่อยมลพิษทางอ้อม"
            else:
                scope_title += "การปล่อยมลพิษ (อื่นๆ)"
            
            # สร้าง style สำหรับ scope title
            scope_header_style = ParagraphStyle(
                f'ScopeHeader{scope["scope"]}',
                parent=scope_title_style,
                textColor=scope_color,
                spaceAfter=15,
                fontName=thai_font_bold
            )
            
            # สร้าง Scope Header ที่อ่านง่าย
            scope_header_data = [[
                scope_title,
                f"{scope['material_count']} รายการ",  
                f"{scope['scope_total']:,.2f} tonCO₂e",
                f"{scope['scope_percentage']:.2f}% ของทั้งหมด"
            ]]
            
            scope_header_table = Table(scope_header_data, colWidths=[3.2*inch, 1.0*inch, 1.3*inch, 2.0*inch])
            scope_header_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), scope_color),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
                ('FONTNAME', (0, 0), (-1, -1), thai_font_bold),
                ('FONTSIZE', (0, 0), (-1, -1), 9),  # ลดขนาด font
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),      # Left align title
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),   # Center align stats
                ('TOPPADDING', (0, 0), (-1, -1), 12),    # ลด padding
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                # ลดความหนาของขอบ
                ('BOX', (0, 0), (-1, -1), 0.8, colors.Color(255/255, 255/255, 255/255, 0.3)),
            ]))
            
            # สร้าง list สำหรับจัดกลุ่ม Scope Header กับ Sub-scopes ทั้งหมด
            scope_elements = [
                scope_header_table,
                Spacer(1, 3)  # ลดช่องว่างจาก 15 เป็น 3
            ]
            
            for sub_scope in scope['sub_scopes']:
                # สร้างกลุ่มของ sub-scope และตารางเพื่อป้องกันการแยกหน้า
                sub_scope_elements = []
                
                # สร้าง Sub-scope Header แยก (เพื่อป้องกันการทับข้อความ)
                sub_scope_title = f"{scope['scope']}.{sub_scope['sub_scope']} - {sub_scope['ghg_name']}"
                
                # ตัดชื่อ sub-scope ถ้ายาวเกินไป
                if len(sub_scope_title) > 80:
                    sub_scope_title = sub_scope_title[:77] + "..."
                
                sub_scope_header_data = [[
                    Paragraph(sub_scope_title, ParagraphStyle(
                        'SubScopeTitle',
                        parent=normal_style,
                        fontName=thai_font_bold,
                        fontSize=10,
                        textColor=scope_color,
                        leading=12
                    )),
                    f"{len(sub_scope['materials'])} รายการ",
                    f"{sub_scope['sub_scope_total']:,.2f} tonCO₂e",
                    f"{sub_scope['sub_scope_percent_scope1_2_3']:.2f}%"
                ]]
                
                sub_scope_header_table = Table(sub_scope_header_data, colWidths=[4.0*inch, 1.0*inch, 1.3*inch, 1.2*inch])
                sub_scope_header_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.Color(248/255, 250/255, 252/255)),
                    ('TEXTCOLOR', (0, 0), (-1, -1), scope_color),
                    ('FONTNAME', (1, 0), (-1, -1), thai_font_bold),  # ยกเว้น column แรกที่ใช้ Paragraph
                    ('FONTSIZE', (1, 0), (-1, -1), 9),
                    ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                    ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),  # เพิ่ม bottom padding จาก 2 เป็น 6 เพื่อให้ตัวอักษรไม่ชิดขอบล่าง
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                    # ไม่ใส่ BOX เพื่อให้ดูเชื่อมกับตารางข้างล่าง
                    ('LINEBEFORE', (0, 0), (0, -1), 0.8, colors.Color(156/255, 163/255, 175/255)),  # เส้นซ้าย
                    ('LINEAFTER', (-1, 0), (-1, -1), 0.8, colors.Color(156/255, 163/255, 175/255)),  # เส้นขวา
                    ('LINEABOVE', (0, 0), (-1, 0), 0.8, colors.Color(156/255, 163/255, 175/255)),  # เส้นบน
                    ('LINEBELOW', (0, 0), (-1, -1), 0.8, colors.Color(156/255, 163/255, 175/255)),  # เส้นล่าง
                ]))
                
                # สร้างตารางข้อมูล Materials แยก
                materials_data = []
                
                # Table Headers - ลด columns ให้เท่ากับ sub-scope header (4 columns)
                materials_data.append(['รายการ', 'TOTAL (tonCO₂e)', '% (SCOPE 1+2)', '% (ALL)'])
                
                # Materials Data
                for mat in sub_scope['materials']:
                    material_name = f"{mat['name']} ({mat['year']})"
                    # ตัดชื่อ material ถ้ายาวเกินไป
                    if len(material_name) > 60:
                        material_name = material_name[:57] + "..."
                        
                    materials_data.append([
                        Paragraph(material_name, ParagraphStyle(
                            'MaterialName',
                            parent=normal_style,
                            fontName=thai_font_name,
                            fontSize=8,
                            leading=10
                        )),
                        f"{mat['result2']:,.2f}",
                        f"{mat['percent_scope1_2']:.2f}",
                        f"{mat['percent_scope1_2_3']:.2f}"
                    ])
                
                # Total row
                materials_data.append([
                    "รวมทั้งหมด",
                    f"{sub_scope['sub_scope_total']:,.2f}",
                    f"{sub_scope['sub_scope_percent_scope1_2']:.2f}",
                    f"{sub_scope['sub_scope_percent_scope1_2_3']:.2f}"
                ])
                
                # สร้างสีพื้นหลังแบบ light สำหรับแต่ละ scope
                scope_bg_colors = {
                    1: colors.Color(249/255, 245/255, 255/255),    # purple-50
                    2: colors.Color(240/255, 253/255, 244/255),    # green-50
                    3: colors.Color(239/255, 246/255, 255/255)     # blue-50
                }
                scope_bg = scope_bg_colors.get(scope['scope'], colors.Color(249/255, 250/255, 251/255))
                
                # สร้างตารางข้อมูล Materials - ปรับความกว้างให้เท่ากับ sub-scope header
                materials_table = Table(materials_data, colWidths=[4.0*inch, 1.0*inch, 1.3*inch, 1.2*inch])
                materials_table.setStyle(TableStyle([
                        # Table Header Row
                        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(243/255, 244/255, 246/255)),  # bg-gray-100
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.Color(55/255, 65/255, 81/255)),  # text-gray-700
                        ('FONTNAME', (0, 0), (-1, 0), thai_font_bold),
                        ('FONTSIZE', (0, 0), (-1, 0), 8),
                        ('ALIGN', (0, 0), (0, 0), 'LEFT'),    # Left align รายการ
                        ('ALIGN', (1, 0), (-1, 0), 'CENTER'), # Center align ตัวเลข
                        ('TOPPADDING', (0, 0), (-1, 0), 6),   # ลด top padding เพื่อให้ติดกับ header ข้างบน
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                        ('LEFTPADDING', (0, 0), (-1, 0), 8),
                        ('RIGHTPADDING', (0, 0), (-1, 0), 8),
                        
                        # Data rows (แถวที่ 2 ถึงก่อนสุดท้าย)
                        ('FONTNAME', (1, 1), (-1, -2), thai_font_name),  # ยกเว้น column แรกที่ใช้ Paragraph
                        ('FONTSIZE', (1, 1), (-1, -2), 8),
                        ('ALIGN', (0, 1), (0, -2), 'LEFT'),    # Left align material names
                        ('ALIGN', (1, 1), (-1, -2), 'CENTER'), # Center align numbers
                        ('VALIGN', (0, 1), (-1, -2), 'MIDDLE'),
                        ('TOPPADDING', (0, 1), (-1, -2), 6),
                        ('BOTTOMPADDING', (0, 1), (-1, -2), 6),
                        ('LEFTPADDING', (0, 1), (-1, -2), 8),
                        ('RIGHTPADDING', (0, 1), (-1, -2), 8),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.Color(249/255, 250/255, 251/255)]),
                        
                        # Total row (แถวสุดท้าย)
                        ('BACKGROUND', (0, -1), (-1, -1), scope_bg),
                        ('FONTNAME', (0, -1), (-1, -1), thai_font_bold),
                        ('FONTSIZE', (0, -1), (-1, -1), 9),
                        ('ALIGN', (0, -1), (0, -1), 'LEFT'),
                        ('ALIGN', (1, -1), (-1, -1), 'CENTER'),
                        ('TOPPADDING', (0, -1), (-1, -1), 10),
                        ('BOTTOMPADDING', (0, -1), (-1, -1), 10),
                        ('LEFTPADDING', (0, -1), (-1, -1), 8),
                        ('RIGHTPADDING', (0, -1), (-1, -1), 8),
                        
                        # Borders - ปรับให้เชื่อมกับ sub-scope header
                        ('GRID', (0, 1), (-1, -1), 0.5, colors.Color(229/255, 231/255, 235/255)),  # เส้นแบ่งข้อมูลบางลง
                        ('LINEABOVE', (0, -1), (-1, -1), 0.8, colors.Color(156/255, 163/255, 175/255)),  # เส้นบนแถว total อ่อนลง
                        # ไม่ใส่ LINEABOVE ที่แถวแรกเพื่อให้ดูเชื่อมกับ sub-scope header
                        ('LINEBEFORE', (0, 0), (0, -1), 0.8, colors.Color(156/255, 163/255, 175/255)),  # เส้นซ้าย
                        ('LINEAFTER', (-1, 0), (-1, -1), 0.8, colors.Color(156/255, 163/255, 175/255)),  # เส้นขวา
                        ('LINEBELOW', (0, -1), (-1, -1), 0.8, colors.Color(156/255, 163/255, 175/255)),  # เส้นล่าง
                        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.Color(203/255, 213/255, 225/255)),  # เส้นใต้ header อ่อนลง
                        
                    # การจัดตำแหน่ง
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))
                
                # เพิ่ม sub-scope header และตารางข้อมูลแบบ KeepTogether
                sub_scope_elements = [
                    sub_scope_header_table,
                    Spacer(1, 1),    # ระยะห่างระหว่าง sub-scope header กับตาราง materials (ปรับได้ตามต้องการ)
                    materials_table,
                    Spacer(1, 20)     # ระยะห่างหลังตาราง materials
                ]
                
                # เพิ่ม sub-scope elements เข้าไปใน scope_elements
                scope_elements.extend([
                    sub_scope_header_table,
                    Spacer(1, 1),    # ระยะห่างระหว่าง sub-scope header กับตาราง
                    materials_table,
                    Spacer(1, 10)    # ระยะห่างหลังตาราง materials
                ])
            
            # จัดกลุ่ม Scope Header กับ Sub-scopes ทั้งหมดไว้ด้วยกัน
            story.append(KeepTogether(scope_elements))
            story.append(Spacer(1, 8))   # ลดช่องว่างระหว่าง scope จาก 12 เป็น 8
        
        # Grand Total (เหมือนหน้าเว็บ - bg-gray-400 text-white)
        story.append(Spacer(1, 8))  # ลดช่องว่างก่อน Grand Total จาก 20 เป็น 8
        
        # สร้าง table สำหรับ Grand Total เพื่อให้เหมือนหน้าเว็บ
        grand_total_data = [[
            f"รวมทั้งหมด ({selected_year}) • {grand_total:,.2f} tonCO₂e • 100% ของทั้งหมด",
            "", "", ""  # ช่องว่างสำหรับ columns อื่น (ลดเหลือ 4 columns)
        ]]
        
        # ปรับความกว้างให้เท่ากับตารางข้างบน (4.0 + 1.0 + 1.3 + 1.2 = 7.5 inch)
        grand_total_table = Table(grand_total_data, colWidths=[4.0*inch, 1.0*inch, 1.3*inch, 1.2*inch])
        grand_total_table.setStyle(TableStyle([
            # รวมทุก columns เป็นหนึ่งเดียว
            ('SPAN', (0, 0), (-1, 0)),
            ('BACKGROUND', (0, 0), (-1, -1), colors.Color(156/255, 163/255, 175/255)),  # bg-gray-400
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), thai_font_name),  # ใช้ font ธรรมดา แทน bold
            ('FONTSIZE', (0, 0), (-1, -1), 12),  # ลดขนาด font จาก 14 เป็น 12
            ('TOPPADDING', (0, 0), (-1, -1), 15),  # ลด padding จาก 18 เป็น 15
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),  # ลด padding จาก 15 เป็น 12
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('BOX', (0, 0), (-1, -1), 0.8, colors.Color(107/255, 114/255, 128/255)),  # ลดความหนาขอบจาก 2 เป็น 0.8
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(grand_total_table)
        
        # Notes Section - ออกแบบให้ดูเป็นทางการ แบบรวมเป็นก้อนเดียว
        if notes:
            story.append(Spacer(1, 25))  # เพิ่มระยะห่าง
            
            # สร้าง Notes Section แบบรวมทั้งหมดเป็นตารางเดียว
            notes_content_style = ParagraphStyle(
                'NotesContent',
                parent=normal_style,
                fontSize=10,
                leading=14,  # ระยะห่างระหว่างบรรทัด
                spaceAfter=6,
                leftIndent=12,
                rightIndent=12,
                fontName=thai_font_name,
                textColor=colors.Color(55/255, 65/255, 81/255),  # text-gray-700
                alignment=4  # justify text
            )
            
            # สร้าง content สำหรับ notes
            note_paragraphs = notes.split('\n')
            formatted_notes = []
            
            for paragraph in note_paragraphs:
                if paragraph.strip():  # ข้าม empty lines
                    # เพิ่มเครื่องหมาย bullet point สำหรับแต่ละย่อหน้า
                    if len([p for p in note_paragraphs if p.strip()]) > 1:
                        formatted_paragraph = f"• {paragraph.strip()}"
                    else:
                        formatted_paragraph = paragraph.strip()
                    formatted_notes.append(formatted_paragraph)
            
            # รวม notes content เป็น string เดียว
            notes_content = '<br/>'.join(formatted_notes)
            
            # สร้างตารางแบบรวม 3 ส่วนเป็นหนึ่งเดียว
            combined_notes_data = [
                # Header row
                ["หมายเหตุและข้อสังเกต (Notes & Observations)"],
                # Content row
                [Paragraph(notes_content, notes_content_style)],
                # Footer row
                [f"หมายเหตุถูกบันทึกเมื่อ: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"]
            ]
            
            combined_notes_table = Table(combined_notes_data, colWidths=[7.5*inch])
            combined_notes_table.setStyle(TableStyle([
                # Header row styling
                ('BACKGROUND', (0, 0), (0, 0), colors.Color(248/255, 249/255, 250/255)),  # bg-gray-50
                ('TEXTCOLOR', (0, 0), (0, 0), colors.Color(17/255, 24/255, 39/255)),  # text-gray-900
                ('FONTNAME', (0, 0), (0, 0), thai_font_bold),
                ('FONTSIZE', (0, 0), (0, 0), 12),
                ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (0, 0), 12),
                ('BOTTOMPADDING', (0, 0), (0, 0), 12),
                ('LEFTPADDING', (0, 0), (0, 0), 15),
                ('RIGHTPADDING', (0, 0), (0, 0), 15),
                ('LINEBELOW', (0, 0), (0, 0), 2.0, colors.Color(59/255, 130/255, 246/255)),  # blue accent line
                
                # Content row styling
                ('BACKGROUND', (0, 1), (0, 1), colors.white),
                ('VALIGN', (0, 1), (0, 1), 'TOP'),
                ('TOPPADDING', (0, 1), (0, 1), 15),
                ('BOTTOMPADDING', (0, 1), (0, 1), 15),
                ('LEFTPADDING', (0, 1), (0, 1), 18),
                ('RIGHTPADDING', (0, 1), (0, 1), 18),
                
                # Footer row styling
                ('BACKGROUND', (0, 2), (0, 2), colors.Color(249/255, 250/255, 251/255)),  # bg-gray-50
                ('TEXTCOLOR', (0, 2), (0, 2), colors.Color(107/255, 114/255, 128/255)),  # text-gray-500
                ('FONTNAME', (0, 2), (0, 2), thai_font_name),
                ('FONTSIZE', (0, 2), (0, 2), 8),
                ('ALIGN', (0, 2), (0, 2), 'RIGHT'),
                ('VALIGN', (0, 2), (0, 2), 'MIDDLE'),
                ('TOPPADDING', (0, 2), (0, 2), 8),
                ('BOTTOMPADDING', (0, 2), (0, 2), 8),
                ('LEFTPADDING', (0, 2), (0, 2), 15),
                ('RIGHTPADDING', (0, 2), (0, 2), 15),
                ('LINEABOVE', (0, 2), (0, 2), 0.5, colors.Color(209/255, 213/255, 219/255)),  # top border
                
                # รอบนอกของตารางทั้งหมด
                ('BOX', (0, 0), (-1, -1), 1.0, colors.Color(209/255, 213/255, 219/255)),  # border-gray-300
                
                # ไม่มีเส้นแบ่งระหว่าง rows เพื่อให้ดูเป็นก้อนเดียว
            ]))
            
            story.append(combined_notes_table)
        
        # สร้าง PDF
        doc.build(story)
        pdf_buffer.seek(0)

        # สร้างชื่อไฟล์
        safe_filename = f"emission_proportions_{selected_year}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        # ถ้าเป็น HTMX request ให้ส่งลิ้งค์ดาวน์โหลดกลับไป
        if is_htmx:
            # สร้าง response สำหรับ HTMX ที่มี JavaScript trigger การดาวน์โหลด
            # สร้าง JavaScript safe strings - แก้ไขให้ handle newlines และ special characters ให้ถูกต้อง
            safe_report_title = report_title.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
            safe_notes = notes.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
            download_url = url_for("proportions.download_pdf")
            
            response_html = f"""
            <div class="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded mb-4">
              <div class="flex items-center">
                <i data-feather="check-circle" class="w-5 h-5 mr-2"></i>
                <div>
                  <strong>สำเร็จ!</strong> รายงาน PDF กำลังดาวน์โหลด...
                  <div class="text-sm mt-1">ไฟล์: {safe_filename}</div>
                </div>
              </div>
            </div>
            <script>
              // Trigger actual file download via JavaScript
              const form = document.createElement('form');
              form.method = 'POST';
              form.action = '{download_url}';
              form.target = '_blank';
              
              const inputs = [
                ['report_title', '{safe_report_title}'],
                ['notes', '{safe_notes}'],
                ['pdf_format', '{pdf_format}'],
                ['year', '{selected_year}']
              ];
              
              inputs.forEach(([name, value]) => {{
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = name;
                input.value = value;
                form.appendChild(input);
              }});
              
              document.body.appendChild(form);
              form.submit();
              document.body.removeChild(form);
              
              if (typeof feather !== 'undefined') {{ feather.replace(); }}
            </script>
            """
            return response_html
        
        # ถ้าไม่ใช่ HTMX request ให้ส่งไฟล์ปกติ
        pdf_buffer.seek(0)
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=safe_filename,
            mimetype='application/pdf'
        )

    except Exception as e:
        # ถ้าเป็น HTMX request ให้ส่งกลับ error message
        return create_htmx_response(
            "emission-proportions/partials/pdf-success.html",
            {"error_message": f"เกิดข้อผิดพลาด: {str(e)}"},
            error_message=f"เกิดข้อผิดพลาด: {str(e)}"
        )


@module.route("/preview-pdf", methods=["POST"])
@login_required
@permissions_required_all(["พรีวิวรายงานสัดส่วนการปล่อย"])
def preview_pdf_data():
    """
    Get PDF preview data
    """
    try:
        # รับข้อมูลจากฟอร์ม
        report_title = request.form.get("report_title", "รายงานสัดส่วนการปล่อยก๊าซเรือนกระจก")
        notes = request.form.get("notes", "")
        selected_year = int(request.form.get("year", datetime.datetime.now().year))
        
        # ดึงข้อมูลเดียวกับหน้าหลัก
        user_campus = current_user.campus_id
        user_department = current_user.department_key
        
        # ดึงข้อมูล materials
        base_year_filter = {
            "campus": user_campus,
            "result2__ne": None,
            "result2__exists": True,
            "year": selected_year,
        }
        if user_department and user_department.strip():
            base_year_filter["department"] = user_department

        materials = Material.objects(**base_year_filter).order_by("scope", "sub_scope", "name")

        # Group by scope/sub_scope (เหมือนกับหน้าหลัก)
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

        # Prepare data for template (เหมือนกับหน้าหลัก)
        scope_data = []
        for scope in sorted(scopes.keys()):
            sub_scopes = []
            for sub_scope in sorted(scopes[scope].keys()):
                # รวม material ที่ชื่อเดียวกัน
                material_dict = {}
                for mat in scopes[scope][sub_scope]:
                    key = mat.name
                    if key in material_dict:
                        material_dict[key]["result2"] += float(mat.result2) if mat.result2 else 0.0
                        # รวม quantity_type ถ้ามี
                        if mat.quantity_type:
                            for qt in mat.quantity_type:
                                material_dict[key]["quantity_info"].append({
                                    "field": qt.field,
                                    "amount": qt.amount,
                                    "unit": qt.unit
                                })
                    else:
                        quantity_info = []
                        if mat.quantity_type:
                            for qt in mat.quantity_type:
                                quantity_info.append({
                                    "field": qt.field,
                                    "amount": qt.amount,
                                    "unit": qt.unit
                                })
                        
                        material_dict[key] = {
                            "name": mat.name,
                            "result2": float(mat.result2) if mat.result2 else 0.0,
                            "quantity_info": quantity_info,
                        }

                # สร้าง materials_list จาก dict
                materials_list = []
                for item in material_dict.values():
                    # คำนวณ percentage ต่าง ๆ เหมือนใน PDF จริง
                    percent_scope1_2 = (
                        (item["result2"] / (scope_totals.get(1, 0) + scope_totals.get(2, 0)) * 100)
                        if (scope_totals.get(1, 0) + scope_totals.get(2, 0)) > 0
                        else 0
                    )
                    percent_scope1_2_3 = (
                        (item["result2"] / grand_total * 100) if grand_total > 0 else 0
                    )
                    
                    materials_list.append({
                        "name": item["name"],
                        "result2": item["result2"],
                        "quantity_info": item["quantity_info"],
                        "percent_scope1_2": percent_scope1_2,
                        "percent_scope1_2_3": percent_scope1_2_3,
                        "year": selected_year,
                    })
                
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
                
                sub_scopes.append({
                    "sub_scope": sub_scope,
                    "ghg_name": ghg_name,
                    "materials": materials_list,
                    "sub_scope_total": sub_scope_total,
                    "sub_scope_percent_scope1": sub_scope_percent_scope1,
                    "sub_scope_percent_scope1_2": sub_scope_percent_scope1_2,
                    "sub_scope_percent_scope1_2_3": sub_scope_percent_scope1_2_3,
                })
            
            scope_data.append({
                "scope": scope,
                "scope_total": scope_totals[scope],
                "material_count": scope_material_counts[scope],
                "scope_percentage": (
                    (scope_totals[scope] / grand_total * 100) if grand_total > 0 else 0
                ),
                "sub_scopes": sub_scopes,
            })

        # สร้าง page_meta
        campus_name = CampusAndDepartment.get_campus_name(user_campus) if hasattr(CampusAndDepartment, "get_campus_name") else user_campus
        department_name = CampusAndDepartment.get_department_name(user_campus, user_department) if user_department else "-"
        
        total_materials = len(materials)
        total_scopes = len(scope_totals.keys())
        scope_coverage = [
            {
                "scope": s,
                "total": scope_totals[s],
                "percent": (scope_totals[s] / grand_total * 100) if grand_total > 0 else 0,
            }
            for s in sorted(scope_totals.keys())
        ]

        page_meta = {
            "title": report_title,
            "description": "สรุปสัดส่วนการปล่อยตาม Scope / Sub-Scope และสัดส่วนต่อภาพรวมทั้งหมด",
            "campus": campus_name,
            "department": department_name,
            "selected_year": selected_year,
            "total_materials": total_materials,
            "total_scopes": total_scopes,
            "grand_total": grand_total,
            "scope_coverage": scope_coverage,
        }

        # สร้าง generated_date สำหรับ preview
        generated_date = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

        return render_template(
            "emission-proportions/partials/pdf-preview.html",
            scope_data=scope_data,
            grand_total=grand_total,
            scope_totals=scope_totals,
            selected_year=selected_year,
            page_meta=page_meta,
            notes=notes,
            generated_date=generated_date
        )

    except Exception as e:
        return create_htmx_response(
            "emission-proportions/partials/pdf-preview.html",
            {"error_message": f"เกิดข้อผิดพลาด: {str(e)}"},
            error_message=f"เกิดข้อผิดพลาด: {str(e)}"
        )


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
