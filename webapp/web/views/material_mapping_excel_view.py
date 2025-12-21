from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, make_response, send_file
from flask_login import login_required, current_user
import openpyxl
import re
from functools import lru_cache
from ...models import CampusAndDepartment, MaterialMappingExcel, FormAndFormula, User
from ..forms.material_mapping_excel_form import MaterialMappingExcelForm, FormChoicesModalForm
from webapp.services.export_excel_service import export_material_mapping_excel_to_download
from ..utils.acl import permissions_required_all

module = Blueprint("material_mapping_excel", __name__, url_prefix="/material-mapping-excel")
@lru_cache(maxsize=128)
def get_keys_by_scope_from_excel(sheet_name="Fr-04.1", file_mtime=None, template_excel_id=None):
    """อ่านและ parse ไฟล์ Excel template เพื่อสร้าง keys_by_scope (มี cache)"""
    import io
    from webapp.models.file_model import TemplateExcel
    
    if not template_excel_id:
        raise ValueError("Template Excel ID is required")
    
    template = TemplateExcel.objects(id=template_excel_id).first()
    if not template or not template.file or not template.file.data:
        raise ValueError(f"Template Excel ID {template_excel_id} not found or has no file data")
    
    file_stream = io.BytesIO(template.file.data)
    wb = openpyxl.load_workbook(file_stream)
    ws = wb[sheet_name]
    
    def get_cell_color(cell):
        fill = cell.fill
        if fill and fill.fgColor and fill.fgColor.type == 'rgb':
            return fill.fgColor.rgb.upper()
        return None
    
    SCOPE_SUB_COLOR = "FFFFC000"
    SUB_SCOPE_ITEM_COLOR = "FFFBD4B4"
    keys_by_scope = {1: {}, 2: {}, 3: {}}
    scope_numbers = {1: {}, 2: {}, 3: {}}
    current_scope = None
    current_sub_scope = None
    current_sub_sub_scope = None
    sub_scope_counters = {1: 0, 2: 0, 3: 0}
    
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
            
            if current_scope == 3:
                match_cat = re.match(r'^(Cat\.?\s*\d+)', current_sub_scope, re.IGNORECASE)
                if match_cat:
                    scope_number = match_cat.group(1).replace('.', '').replace(' ', ' ').strip()
                    scope_number = re.sub(r'Cat\s*', 'Cat ', scope_number, flags=re.IGNORECASE)
                else:
                    sub_scope_counters[current_scope] += 1
                    scope_number = f"Cat {sub_scope_counters[current_scope]}"
            else:
                sub_scope_counters[current_scope] += 1
                scope_number = f"{current_scope}.{sub_scope_counters[current_scope]}"
            
            if current_sub_scope not in keys_by_scope[current_scope]:
                keys_by_scope[current_scope][current_sub_scope] = {}
                scope_numbers[current_scope][current_sub_scope] = scope_number
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
    
    return keys_by_scope, scope_numbers

@module.route("/", methods=["GET"])
@login_required
#@permissions_required_all(["จัดการ mapping excel"])
def mapping_excel_view():
    campus_id = request.args.get('campus_id') or current_user.campus_id
    department_key = request.args.get('department_key') or current_user.department_key
    year = request.args.get("year", 2025, type=int)
    sheet_name = "Fr-04.1"
    
    campus = CampusAndDepartment.objects.get(id=campus_id)
    department_name = campus.departments.get(department_key, "ไม่ทราบหน่วยงาน")
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
    
    if not mapping_doc.template_excel_id:
        flash("กรุณาเลือกไฟล์ต้นฉบับก่อนแก้ไข Mapping", "warning")
        return redirect(url_for('material_mapping_excel_management.admin_mapping_excel_view'))
    from webapp.models.file_model import TemplateExcel
    template = TemplateExcel.objects(id=mapping_doc.template_excel_id).first()
    if not template:
        flash("ไม่พบไฟล์ต้นฉบับที่เลือก", "error")
        return redirect(url_for('material_mapping_excel_management.admin_mapping_excel_view'))
    
    db_mtime = template.file.upload_date.timestamp() if template and template.file else None
    user = User.objects.with_id(current_user.id)
    selected_subscopes = {
        1: user.ghg_scope_1 or [],
        2: user.ghg_scope_2 or [],
        3: user.ghg_scope_3 or []
    }
    
    all_forms = list(FormAndFormula.objects.only('id', 'material_name', 'ghg_scope', 'ghg_sup_scope'))
    form_and_formula_dict = {str(f.id): f for f in all_forms}
    
    form_choices_by_scope = {1: [], 2: [], 3: []}
    for scope_num in [1, 2, 3]:
        scope_forms = [
            (str(f.id), f.material_name) 
            for f in all_forms 
            if f.ghg_scope == scope_num and f.ghg_sup_scope in selected_subscopes[scope_num]
        ]
        form_choices_by_scope[scope_num] = sorted(scope_forms, key=lambda x: x[1])
    
    try:
        keys_by_scope, scope_numbers = get_keys_by_scope_from_excel(sheet_name, db_mtime, mapping_doc.template_excel_id)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for('material_mapping_excel_management.admin_mapping_excel_view'))
    
    return render_template(
        "material-mapping-excel/mapping-excel-view.html",
        mapping_doc=mapping_doc,
        form_choices_by_scope=form_choices_by_scope,
        keys_by_scope=keys_by_scope,
        scope_numbers=scope_numbers,
        form_and_formula_dict=form_and_formula_dict,
        campus=campus,
        department_name=department_name,
        campus_id=campus_id,
        department_key=department_key
    )

@module.route("/edit", methods=["GET", "POST"])
@login_required
#@permissions_required_all(["แก้ไข mapping excel"])
def mapping_excel_edit():
    campus_id = request.args.get('campus_id') or current_user.campus_id
    department_key = request.args.get('department_key') or current_user.department_key
    year = request.args.get("year", 2025, type=int)
    sheet_name = "Fr-04.1"
    
    campus = CampusAndDepartment.objects.get(id=campus_id)
    department_name = campus.departments.get(department_key, "ไม่ทราบหน่วยงาน")
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
    
    if not mapping_doc.template_excel_id:
        flash("กรุณาเลือกไฟล์ต้นฉบับก่อนแก้ไข Mapping", "warning")
        return redirect(url_for('material_mapping_excel_management.admin_mapping_excel_view'))
    
    from webapp.models.file_model import TemplateExcel
    template = TemplateExcel.objects(id=mapping_doc.template_excel_id).first()
    if not template:
        flash("ไม่พบไฟล์ต้นฉบับที่เลือก", "error")
        return redirect(url_for('material_mapping_excel_management.admin_mapping_excel_view'))
    
    db_mtime = template.file.upload_date.timestamp() if template and template.file else None
    
    try:
        keys_by_scope, scope_numbers = get_keys_by_scope_from_excel(sheet_name, db_mtime, mapping_doc.template_excel_id)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for('material_mapping_excel_management.admin_mapping_excel_view'))

    user = User.objects.with_id(current_user.id)
    selected_subscopes = {
        1: user.ghg_scope_1 or [],
        2: user.ghg_scope_2 or [],
        3: user.ghg_scope_3 or []
    }
    
    all_forms = list(FormAndFormula.objects.only('id', 'material_name', 'ghg_scope', 'ghg_sup_scope'))
    form_and_formula_dict = {str(f.id): f for f in all_forms}
    
    form_choices_by_scope = {1: [], 2: [], 3: []}
    for scope_num in [1, 2, 3]:
        scope_forms = [
            (str(f.id), f.material_name) 
            for f in all_forms 
            if f.ghg_scope == scope_num and f.ghg_sup_scope in selected_subscopes[scope_num]
        ]
        form_choices_by_scope[scope_num] = sorted(scope_forms, key=lambda x: x[1])

    form = MaterialMappingExcelForm()

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
                scope_numbers=scope_numbers,
                form_choices_by_scope=form_choices_by_scope,
                form=form,
                mapping_doc=mapping_doc,
                form_and_formula_dict=form_and_formula_dict,
                campus=campus,
                department_name=department_name,
                campus_id=campus_id,
                department_key=department_key
            ))
            response.headers["HX-Trigger"] = '{"showSuccess": "บันทึกข้อมูล Mapping สำเร็จ"}'
            return response
        except Exception as e:
            response = make_response(render_template(
                "material-mapping-excel/mapping-excel-edit.html",
                keys_by_scope=keys_by_scope,
                scope_numbers=scope_numbers,
                form_choices_by_scope=form_choices_by_scope,
                form=form,
                mapping_doc=mapping_doc,
                form_and_formula_dict=form_and_formula_dict,
                campus=campus,
                department_name=department_name,
                campus_id=campus_id,
                department_key=department_key
            ))
            response.headers["HX-Trigger"] = '{"showError": "บันทึกข้อมูลไม่สำเร็จ"}'
            return response
    return render_template(
        "material-mapping-excel/mapping-excel-edit.html",
        keys_by_scope=keys_by_scope,
        scope_numbers=scope_numbers,
        form_choices_by_scope=form_choices_by_scope,
        form=form,
        mapping_doc=mapping_doc,
        form_and_formula_dict=form_and_formula_dict,
        campus=campus,
        department_name=department_name,
        campus_id=campus_id,
        department_key=department_key
    )

@module.route("/form-choices-modal", methods=["GET", "POST"])
@login_required
def form_choices_modal():
    if request.method == "GET" and not request.headers.get("HX-Request"):
        abort(404)
    scope_num = int(request.args.get("scope_num"))
    key = request.args.get("key")
    encoded_key = request.args.get("encoded_key", "")
    sub_scope_index = int(request.args.get("sub_scope_index", 0) or 0)
    
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
    
    campus_id = request.args.get("campus_id") or current_user.campus_id
    department_key = request.args.get("department_key") or current_user.department_key
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
        for i in mapping_doc.mappings[key]:
            selected_ids.append(i["id"] if isinstance(i, dict) and "id" in i else i)
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
    
    campus_id = request.form.get("campus_id") or current_user.campus_id
    department_key = request.form.get("department_key") or current_user.department_key
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
    
    mappings = mapping_doc.mappings or {}
    mappings[key] = selected_ids
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
        form_and_formula_dict=form_and_formula_dict,
        sub_scope_index=request.form.get("sub_scope_index", 0),
        campus_id=campus_id,
        department_key=department_key,
        year=year
    ))
    response.headers["HX-Trigger"] = '{"closeModal": true, "showSuccess": "success"}'
    return response

@module.route("/export-excel", methods=["GET"])
@login_required
#@permissions_required_all(["ดาวน์โหลด mapping excel"])
def export_excel():
    campus_id = request.args.get('campus_id') or current_user.campus_id
    department_key = request.args.get('department_key') or current_user.department_key
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
