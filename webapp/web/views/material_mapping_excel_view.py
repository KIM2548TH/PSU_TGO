from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, make_response, send_file
from flask_login import login_required, current_user
import openpyxl
import os
import urllib.parse
from ...models import CampusAndDepartment, Material, MaterialMappingExcel, FormAndFormula, Scope, User
from ..forms.material_mapping_excel_form import MaterialMappingExcelForm, FormChoicesModalForm
from wtforms import FieldList, HiddenField
from webapp.services.export_excel_service import export_material_mapping_excel, export_material_mapping_excel_to_download

module = Blueprint("material_mapping_excel", __name__, url_prefix="/material-mapping-excel")

@module.route("/", methods=["GET"])
@login_required
def mapping_excel_view():
    campus_id = current_user.campus_id
    department_key = current_user.department_key
    year = request.args.get("year", 2025, type=int)
    sheet_name = "Fr-04.1"
    mapping_doc = MaterialMappingExcel.objects(
        campus_id=campus_id,
        department_key=department_key,
        year=year,
        sheet_name=sheet_name
    ).first()
    if not mapping_doc:
        mapping_doc = MaterialMappingExcel(
            campus_id=campus_id,
            department_key=department_key,
            year=year,
            sheet_name=sheet_name,
            mappings={}
        )
        mapping_doc.save()
    # ดึง scope/sub-scope ที่ผู้ใช้ในคณะนี้ติ๊กไว้
    user = User.objects.with_id(current_user.id)
    selected_subscopes = {
        1: user.ghg_scope_1 or [],
        2: user.ghg_scope_2 or [],
        3: user.ghg_scope_3 or []
    }
    form_choices_by_scope = {1: [], 2: [], 3: []}
    for scope_num in [1, 2, 3]:
        for sub_scope in selected_subscopes[scope_num]:
            forms = FormAndFormula.objects(ghg_scope=scope_num, ghg_sup_scope=sub_scope)
            for f in forms:
                form_choices_by_scope[scope_num].append((str(f.id), f.material_name))
        form_choices_by_scope[scope_num] = sorted(form_choices_by_scope[scope_num], key=lambda x: x[1])
    # สร้าง dict id -> FormAndFormula object
    form_and_formula_dict = {str(f.id): f for f in FormAndFormula.objects()}
    # สร้าง keys_by_scope เหมือนหน้า edit
    template_path = os.path.join(os.path.dirname(__file__), "../../tamplate_file/การคำนวณCFO.xlsx")
    wb = openpyxl.load_workbook(template_path)
    ws = wb[sheet_name]
    def get_cell_color(cell):
        fill = cell.fill
        if fill and fill.fgColor and fill.fgColor.type == 'rgb':
            return fill.fgColor.rgb.upper()
        return None
    SCOPE_SUB_COLOR = "FFFFC000"
    SUB_SCOPE_ITEM_COLOR = "FFFBD4B4"
    keys_by_scope = {1: {}, 2: {}, 3: {}}
    current_scope = None
    current_sub_scope = None
    current_sub_sub_scope = None
    for row in ws.iter_rows(min_row=2, max_col=4):
        col_a = row[0].value
        cell_b = row[1]
        col_b = cell_b.value
        cell_b_color = get_cell_color(cell_b)
        if col_a:
            col_a_str = str(col_a)
            if "ขอบเขต 1" in col_a_str:
                current_scope = 1
                current_sub_scope = None
                current_sub_sub_scope = None
            elif "ขอบเขต 2" in col_a_str:
                current_scope = 2
                current_sub_scope = None
                current_sub_sub_scope = None
            elif "ขอบเขต 3" in col_a_str:
                current_scope = 3
                current_sub_scope = None
                current_sub_sub_scope = None
        if current_scope and col_b and cell_b_color == SCOPE_SUB_COLOR:
            current_sub_scope = str(col_b).strip()
            if current_sub_scope not in keys_by_scope[current_scope]:
                keys_by_scope[current_scope][current_sub_scope] = {}
            current_sub_sub_scope = None
        elif current_scope and col_b and cell_b_color == SUB_SCOPE_ITEM_COLOR:
            current_sub_sub_scope = str(col_b).strip()
            if current_sub_scope and current_sub_sub_scope not in keys_by_scope[current_scope][current_sub_scope]:
                keys_by_scope[current_scope][current_sub_scope][current_sub_sub_scope] = []
        elif current_scope and current_sub_scope and col_b and (cell_b_color is None or cell_b_color in ["FFFFFFFF", "#FFFFFF", "00000000"] ) and str(col_b).strip() != "":
            if not current_sub_sub_scope:
                current_sub_sub_scope = "-"
                if current_sub_scope and current_sub_sub_scope not in keys_by_scope[current_scope][current_sub_scope]:
                    keys_by_scope[current_scope][current_sub_scope][current_sub_sub_scope] = []
            keys_by_scope[current_scope][current_sub_scope][current_sub_sub_scope].append(str(col_b).strip())
    return render_template(
        "material-mapping-excel/mapping-excel-view.html",
        mapping_doc=mapping_doc,
        form_choices_by_scope=form_choices_by_scope,
        keys_by_scope=keys_by_scope,
        form_and_formula_dict=form_and_formula_dict
    )

@module.route("/edit", methods=["GET", "POST"])
@login_required
def mapping_excel_edit():
    campus_id = current_user.campus_id
    department_key = current_user.department_key
    year = request.args.get("year", 2025, type=int)
    sheet_name = "Fr-04.1"
    template_path = os.path.join(os.path.dirname(__file__), "../../tamplate_file/การคำนวณCFO.xlsx")
    wb = openpyxl.load_workbook(template_path)
    ws = wb[sheet_name]

    def get_cell_color(cell):
        fill = cell.fill
        if fill and fill.fgColor and fill.fgColor.type == 'rgb':
            return fill.fgColor.rgb.upper()
        return None

    SCOPE_SUB_COLOR = "FFFFC000"  # #ffc000
    SUB_SCOPE_ITEM_COLOR = "FFFBD4B4"  # #fbd4b4

    keys_by_scope = {1: {}, 2: {}, 3: {}}
    current_scope = None
    current_sub_scope = None
    current_sub_sub_scope = None
    for row in ws.iter_rows(min_row=2, max_col=4):
        col_a = row[0].value
        cell_b = row[1]
        col_b = cell_b.value
        cell_b_color = get_cell_color(cell_b)
        # ตรวจสอบหัวข้อขอบเขต
        if col_a:
            col_a_str = str(col_a)
            if "ขอบเขต 1" in col_a_str:
                current_scope = 1
                current_sub_scope = None
                current_sub_sub_scope = None
            elif "ขอบเขต 2" in col_a_str:
                current_scope = 2
                current_sub_scope = None
                current_sub_sub_scope = None
            elif "ขอบเขต 3" in col_a_str:
                current_scope = 3
                current_sub_scope = None
                current_sub_sub_scope = None
        # ถ้า cell ช่อง B มีสี #ffc000 → เป็นชื่อซับสโคป
        if current_scope and col_b and cell_b_color == SCOPE_SUB_COLOR:
            current_sub_scope = str(col_b).strip()
            if current_sub_scope not in keys_by_scope[current_scope]:
                keys_by_scope[current_scope][current_sub_scope] = {}
            current_sub_sub_scope = None
        # ถ้า cell ช่อง B มีสี #fbd4b4 → เป็นชื่อหัวข้อย่อย
        elif current_scope and col_b and cell_b_color == SUB_SCOPE_ITEM_COLOR:
            current_sub_sub_scope = str(col_b).strip()
            if current_sub_scope and current_sub_sub_scope not in keys_by_scope[current_scope][current_sub_scope]:
                keys_by_scope[current_scope][current_sub_scope][current_sub_sub_scope] = []
        # ถ้า cell ช่อง B ไม่มีสี (None) หรือสีขาว #ffffff หรือสีดำ #00000000 → เป็นรายการย่อยที่ต้องแมป (ข้ามเฉพาะ cell ที่ว่างจริง ๆ)
        elif current_scope and current_sub_scope and col_b and (cell_b_color is None or cell_b_color in ["FFFFFFFF", "#FFFFFF", "00000000"] ) and str(col_b).strip() != "":
            # ถ้าไม่มีหัวข้อย่อย ให้สร้างหัวข้อย่อยอัตโนมัติเป็น '-'
            if not current_sub_sub_scope:
                current_sub_sub_scope = "-"
                if current_sub_scope and current_sub_sub_scope not in keys_by_scope[current_scope][current_sub_scope]:
                    keys_by_scope[current_scope][current_sub_scope][current_sub_sub_scope] = []
            keys_by_scope[current_scope][current_sub_scope][current_sub_sub_scope].append(str(col_b).strip())

    # ดึง scope/sub-scope ที่ผู้ใช้ในคณะนี้ติ๊กไว้
    user = User.objects.with_id(current_user.id)
    selected_subscopes = {
        1: user.ghg_scope_1 or [],
        2: user.ghg_scope_2 or [],
        3: user.ghg_scope_3 or []
    }
    # ดึง FormAndFormula ทุกอันในขอบเขตนั้น ๆ (scope/sub-scope)
    form_choices_by_scope = {1: [], 2: [], 3: []}
    for scope_num in [1, 2, 3]:
        for sub_scope in selected_subscopes[scope_num]:
            forms = FormAndFormula.objects(ghg_scope=scope_num, ghg_sup_scope=sub_scope)
            for f in forms:
                form_choices_by_scope[scope_num].append((str(f.id), f.material_name))
        # sort by material_name
        form_choices_by_scope[scope_num] = sorted(form_choices_by_scope[scope_num], key=lambda x: x[1])
    # สร้าง dict id -> FormAndFormula object
    form_and_formula_dict = {str(f.id): f for f in FormAndFormula.objects()}
    
    # ดึงหรือสร้าง MaterialMappingExcel
    mapping_doc = MaterialMappingExcel.objects(
        campus_id=campus_id,
        department_key=department_key,
        year=year,
        sheet_name=sheet_name
    ).first()
    if not mapping_doc:
        mapping_doc = MaterialMappingExcel(
            campus_id=campus_id,
            department_key=department_key,
            year=year,
            sheet_name=sheet_name,
            mappings={}
        )
        mapping_doc.save()

    form = MaterialMappingExcelForm()
    # สร้างฟิลด์แบบไดนามิกสำหรับแต่ละ scope/sub-scope/sub-sub-scope
    for scope_num in [1, 2, 3]:
        for sub_scope_title, sub_sub_dict in keys_by_scope[scope_num].items():
            for sub_sub_title, items in sub_sub_dict.items():
                for key in items:
                    encoded_key = key.replace(' ', '_').replace('.', '_').replace('+', '_')
                    field_name = f"material_{scope_num}_{encoded_key}"
                    if not hasattr(form, field_name):
                        setattr(form, field_name, FieldList(HiddenField(), min_entries=0))
    # ไม่ต้องเติมค่า default hidden field ใน form object
    # ให้ render hidden input ใน template โดยใช้ mapping_doc.mappings

    if form.validate_on_submit():
        mappings = {}
        for scope_num in [1, 2, 3]:
            for sub_scope_title, sub_sub_dict in keys_by_scope[scope_num].items():
                for sub_sub_title, items in sub_sub_dict.items():
                    for key in items:
                        encoded_key = key.replace(' ', '_').replace('.', '_').replace('+', '_')
                        field_name = f"material_{scope_num}_{encoded_key}"
                        ids = request.form.getlist(field_name)
                        mappings[key] = ids  # เก็บเป็น list ของ id string
        try:
            mapping_doc.mappings = mappings
            mapping_doc.updated_date = mapping_doc.updated_date.now()
            mapping_doc.save()
            response = make_response(render_template(
                "material-mapping-excel/mapping-excel-edit.html",
                keys_by_scope=keys_by_scope,
                form_choices_by_scope=form_choices_by_scope,
                form=form,
                mapping_doc=mapping_doc,
                form_and_formula_dict=form_and_formula_dict
            ))
            response.headers["HX-Trigger"] = '{"showSuccess": "บันทึกข้อมูล Mapping สำเร็จ"}'
            return response
        except Exception as e:
            response = make_response(render_template(
                "material-mapping-excel/mapping-excel-edit.html",
                keys_by_scope=keys_by_scope,
                form_choices_by_scope=form_choices_by_scope,
                form=form,
                mapping_doc=mapping_doc,
                form_and_formula_dict=form_and_formula_dict
            ))
            response.headers["HX-Trigger"] = '{"showError": "บันทึกข้อมูลไม่สำเร็จ"}'
            return response
    return render_template(
        "material-mapping-excel/mapping-excel-edit.html",
        keys_by_scope=keys_by_scope,
        form_choices_by_scope=form_choices_by_scope,
        form=form,
        mapping_doc=mapping_doc,
        form_and_formula_dict=form_and_formula_dict
    )

@module.route("/form-choices-modal", methods=["GET", "POST"])
@login_required
def form_choices_modal():
    if request.method == "GET" and not request.headers.get("HX-Request"):
        abort(404)
    scope_num = int(request.args.get("scope_num"))
    key = request.args.get("key")
    encoded_key = request.args.get("encoded_key", "")
    sub_scope_index = request.args.get("sub_scope_index")
    if sub_scope_index is None:
        sub_scope_index = 0
    else:
        sub_scope_index = int(sub_scope_index)
    # ดึงฟอร์มทั้งหมดของ scope_num แล้วจัดกลุ่มตามซับสโคป
    user = User.objects.with_id(current_user.id)
    selected_subscopes = {
        1: user.ghg_scope_1 or [],
        2: user.ghg_scope_2 or [],
        3: user.ghg_scope_3 or []
    }
    grouped_forms = {}
    for sub in selected_subscopes[scope_num]:
        forms = FormAndFormula.objects(ghg_scope=scope_num, ghg_sup_scope=sub)
        grouped_forms[sub] = [(str(f.id), f.material_name) for f in forms]
    # ...existing code...
    campus_id = current_user.campus_id
    department_key = current_user.department_key
    year = request.args.get("year", 2025, type=int)
    sheet_name = "Fr-04.1"
    mapping_doc = MaterialMappingExcel.objects(
        campus_id=campus_id,
        department_key=department_key,
        year=year,
        sheet_name=sheet_name
    ).first()
    selected_ids = []
    if mapping_doc and key in mapping_doc.mappings:
        selected_ids = []
        for i in mapping_doc.mappings[key]:
            if isinstance(i, dict) and "id" in i:
                selected_ids.append(i["id"])
            else:
                selected_ids.append(i)
    form = FormChoicesModalForm()
    if request.method == "POST" and form.validate_on_submit():
        selected = request.form.getlist("form_choices")
        if mapping_doc:
            mapping_doc.mappings[key] = selected
            mapping_doc.updated_date = mapping_doc.updated_date.now()
            mapping_doc.save()
        response = make_response("")
        response.headers["HX-Trigger"] = '{"showSuccess": "success", "closeModal": true}'
        return response
    return render_template(
        "material-mapping-excel/partials/modal-form-choices.html",
        grouped_forms=grouped_forms,
        selected_ids=selected_ids,
        submit_url=url_for("material_mapping_excel.form_choices_modal", scope_num=scope_num, key=key),
        scope_num=scope_num,
        key=key,
        encoded_key=encoded_key,
        sub_scope_index=sub_scope_index,
        form=form
    )

@module.route("/update-row", methods=["POST"])
@login_required
def update_row():
    key = request.form.get("key")
    encoded_key = request.form.get("encoded_key")
    selected_scope_val = request.form.get("scope")
    selected_scope = int(selected_scope_val) if selected_scope_val else 1
    selected_ids = request.form.getlist("form_choices") or request.form.getlist("selected_ids")
    campus_id = current_user.campus_id
    department_key = current_user.department_key
    year = request.form.get("year", 2025, type=int)
    sheet_name = "Fr-04.1"
    mapping_doc = MaterialMappingExcel.objects(
        campus_id=campus_id,
        department_key=department_key,
        year=year,
        sheet_name=sheet_name
    ).first()
    if not mapping_doc:
        return "ไม่พบข้อมูล Mapping", 404
    # อัปเดตเฉพาะ key ที่แก้ไข โดยไม่ลบ key อื่น
    mappings = mapping_doc.mappings or {}
    if key not in mappings or not isinstance(mappings[key], list):
        mappings[key] = []
    # เก็บเป็น list ของ dict {"id": <material_id>}
    mappings[key] = [{"id": mid} for mid in selected_ids]
    mapping_doc.mappings = mappings
    mapping_doc.updated_date = mapping_doc.updated_date.now()
    mapping_doc.save()
    from webapp.models.form_and_formula_model import FormAndFormula
    form_and_formula_dict = {str(f.id): f for f in FormAndFormula.objects()}
    from flask import make_response
    response = make_response(render_template(
        "material-mapping-excel/partials/mapping-row.html",
        key=key,
        selected_ids=selected_ids,
        selected_scope=selected_scope,
        encoded_key=encoded_key,
        form_and_formula_dict=form_and_formula_dict
    ))
    response.headers["HX-Trigger"] = '{"closeModal": true, "showSuccess": "success"}'
    return response

@module.route("/export-excel", methods=["GET"])
@login_required
def export_excel():
    campus_id = current_user.campus_id
    department_key = current_user.department_key
    year = request.args.get("year", 2025, type=int)
    sheet_name = "Fr-04.1"
    input_excel_path = "webapp/tamplate_file/การคำนวณCFO.xlsx"
    output = export_material_mapping_excel_to_download(
        campus_id, department_key, year, sheet_name, input_excel_path
    )
    return send_file(
        output,
        as_attachment=True,
        download_name="exported_material_mapping.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
