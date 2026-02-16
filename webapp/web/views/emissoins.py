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
from ...models.materail_model import Material, QuantityType  # เพิ่ม import QuantityType
from ..forms.material_form import MaterialForm, validate_material_data
from ..utils.acl import permissions_required_all
import datetime
import re
from ...models.file_model import ReferenceDocument, UploadedFile
from urllib.parse import quote
from flask import make_response
import json
import urllib.parse

module = Blueprint("emissions", __name__, url_prefix="/emissions")


def get_user_scopes():
    """
    Get all available scopes for current user
    Returns a list of dictionaries with scope information
    """
    try:
        user_scopes = []

        # Get user's scope permissions from user model
        user = current_user

        # Combine all scopes from all three scope categories
        all_scope_numbers = []
        if hasattr(user, "ghg_scope_1") and user.ghg_scope_1:
            all_scope_numbers.extend([(1, sub_scope) for sub_scope in user.ghg_scope_1])
        if hasattr(user, "ghg_scope_2") and user.ghg_scope_2:
            all_scope_numbers.extend([(2, sub_scope) for sub_scope in user.ghg_scope_2])
        if hasattr(user, "ghg_scope_3") and user.ghg_scope_3:
            all_scope_numbers.extend([(3, sub_scope) for sub_scope in user.ghg_scope_3])

        # Sort by scope number then sub scope number
        all_scope_numbers.sort(key=lambda x: (x[0], x[1]))

        # Get scope details for each available scope
        for scope_num, sub_scope_num in all_scope_numbers:
            scope = Scope.objects(
                ghg_scope=scope_num,
                ghg_sup_scope=sub_scope_num,
                campus=user.campus_id,
                department=user.department_key,
            ).first()

            if scope:
                user_scopes.append(
                    {
                        "scope_id": scope_num,
                        "sub_scope_id": sub_scope_num,
                        "ghg_name": scope.ghg_name,
                        "display_name": f"Scope {scope_num}.{sub_scope_num}",
                    }
                )

        return user_scopes

    except Exception as e:
        return []


def get_current_scope_index(user_scopes, scope_id, sub_scope_id):
    """
    Find the index of current scope in user_scopes list
    """
    try:
        for i, scope in enumerate(user_scopes):
            if scope["scope_id"] == scope_id and scope["sub_scope_id"] == sub_scope_id:
                return i
        return -1
    except Exception as e:
        return -1


def calculate_grouped_input_types(head_table, page):
    """
    Calculate and group input types by headers for pagination.

    Args:
        head_table (list): List of headers from scope.
        items_per_page (int): Number of items per page.
        page (int): Current page number.

    Returns:
        tuple: (current_headers, materials_form, total_pages)
    """
    items_per_page = 8  # จำนวนรายการต่อหน้า
    
    # Optimization: Fetch all forms in one query
    forms = FormAndFormula.objects(material_name__in=head_table)
    form_map = {f.material_name: f for f in forms}
    
    all_input_types = []
    for head in head_table:
        form_and_formula_item = form_map.get(head)
        if form_and_formula_item:
            all_input_types.extend(
                [(head, input_type) for input_type in form_and_formula_item.input_types]
            )

    total_subcategories = len(all_input_types)
    total_pages = (total_subcategories + items_per_page - 1) // items_per_page

    # Determine which subcategories to display on current page
    start_index = (page - 1) * items_per_page
    end_index = min(start_index + items_per_page, total_subcategories)

    current_input_types = all_input_types[start_index:end_index]

    # Group input types by their headers
    grouped_input_types = {}
    for head, input_type in current_input_types:
        if head not in grouped_input_types:
            grouped_input_types[head] = []
        grouped_input_types[head].append(input_type)

    current_headers = list(grouped_input_types.keys())
    materials_form = list(grouped_input_types.values())

    return current_headers, materials_form, total_pages, items_per_page


@module.route("/emissions-table", methods=["POST"])
@login_required
# @permissions_required_all(["เข้าถึงหน้าข้อมูลการปล่อย"])
def view_emissions():
    # รับค่า scope_id และ sub_scope_id จาก POST request
    scope_id = request.form.get("scope_id")
    sub_scope_id = request.form.get("sub_scope_id")
    selected_year = request.form.get("year_form_scope")
    quick_edit = request.form.get("quick_edit", "false").lower() == "true"

    # ดึงปีจาก Material
    years = sorted(Material.objects().distinct("year"))
    # ถ้ามีปีใน database ใช้ปีแรก, ถ้าไม่มีให้ใช้ปีปัจจุบัน
    start_year = years[0] if years else datetime.datetime.now().year
    # ปีปัจจุบัน
    current_year = datetime.datetime.now().year
    years = list(range(start_year, current_year + 1))
    scope = Scope.objects(
        ghg_scope=int(scope_id),
        ghg_sup_scope=int(sub_scope_id),
        department=current_user.department_key,
        campus=current_user.campus_id,
    ).first()
    if scope:
        ghg_name = scope.ghg_name
    else:
        ghg_name = "Unknown Scope"

    # Get all available scopes for user
    user_scopes = get_user_scopes()

    # Find current scope index for navigation
    current_scope_index = -1
    for i, user_scope in enumerate(user_scopes):
        if user_scope["scope_id"] == int(scope_id) and user_scope[
            "sub_scope_id"
        ] == int(sub_scope_id):
            current_scope_index = i
            break

    return render_template(
        "emissions-scope/view-emissions.html",
        scope_id=scope_id,
        sub_scope_id=sub_scope_id,
        user=current_user,
        years=years,
        ghg_name=ghg_name,
        current_year=current_year,
        selected_year=int(selected_year),
        user_scopes=user_scopes,
        current_scope_index=current_scope_index,
        quick_edit=quick_edit,
    )


@module.route("/load-emissions-table", methods=["GET", "POST"])
@login_required
def load_emissions_table():
    scope_id = request.args.get("scope_id")
    sub_scope_id = request.args.get("sub_scope_id")

    year = request.args.get("year") or datetime.datetime.now().year
    page = int(request.args.get("page", 1))

    # Check for quick_edit parameter from both args and form data
    quick_edit_param = request.args.get("quick_edit") or request.form.get("quick_edit")
    quick_edit = False

    # Multiple ways to check for quick_edit
    if quick_edit_param:
        if isinstance(quick_edit_param, str):
            quick_edit = quick_edit_param.lower() == "true"
        elif quick_edit_param is True:
            quick_edit = True

    scope = Scope.objects(
        ghg_scope=int(scope_id),
        ghg_sup_scope=int(sub_scope_id),
        campus=current_user.campus_id,
        department=current_user.department_key,
    ).first()
    if not scope:
        return render_template(
            "emissions-scope/partials/error.html", error="Scope not found"
        )

    head_table = scope.head_table

    # Use new function to calculate grouped input types
    current_headers, materials_form, total_pages, items_per_page = (
        calculate_grouped_input_types(head_table, page)
    )

    # ดึงข้อมูลฟอร์มสำหรับแต่ละ header (Optimized)
    forms = FormAndFormula.objects(material_name__in=current_headers)
    form_map = {f.material_name: f for f in forms}
    
    head_table_info = {}
    for head in current_headers:
        form = form_map.get(head)
        if form:
            head_table_info[head] = {
                "is_linked": getattr(form, "is_linked", False),
                "linked_forms": getattr(form, "linked_forms", []),
                "desc_form": form.desc_form,
                "formula": form.formula,
            }

    materials = Material.objects(
        scope=int(scope_id),
        sub_scope=int(sub_scope_id),
        year=int(year),
        department=current_user.department_key,
        campus=current_user.campus_id,
    )

    # Get all available scopes for user
    user_scopes = get_user_scopes()

    # Find current scope index for navigation
    current_scope_index = -1
    for i, user_scope in enumerate(user_scopes):
        if user_scope["scope_id"] == int(scope_id) and user_scope[
            "sub_scope_id"
        ] == int(sub_scope_id):
            current_scope_index = i
            break

    # Choose template based on edit mode
    template_name = (
        "emissions-scope/partials/quick-edit-table.html"
        if quick_edit
        else "emissions-scope/partials/emissions-table.html"
    )

    return render_template(
        template_name,
        scope=scope,
        scope_id=scope_id,
        sub_scope_id=sub_scope_id,
        materials=materials,
        head_table=current_headers,
        head_table_info=head_table_info,
        total_pages=total_pages,
        page=page,
        user=current_user,
        year=year,
        materials_form=materials_form,
        items_per_page=items_per_page,
        user_scopes=user_scopes,
        current_scope_index=current_scope_index,
    )


@module.route("/load-material-form", methods=["GET"])
@login_required
def load_material_form():
    month_id = request.args.get("month_id")
    head = request.args.get("head")
    year = request.args.get("year")
    month = request.args.get("month")
    amount = request.args.get("amount")
    input_label = request.args.get("input_label")
    input_field = request.args.get("input_field")
    sub_scope_id = request.args.get("sub_scope_id")
    scope_id = request.args.get("scope_id")
    unit = request.args.get("input_unit")

    return render_template(
        "emissions-scope/partials/material-form.html",
        month_id=month_id,
        head=head,
        year=year,
        month=month,
        user=current_user,
        amount=amount,
        input_label=input_label,
        input_field=input_field,
        sub_scope_id=sub_scope_id,
        scope_id=scope_id,
        unit=unit,
    )


@module.route("/load-materials-form", methods=["GET"])
@login_required
def load_materials_form():
    month_id = request.args.get("month_id")
    year = request.args.get("year")
    scope_id = request.args.get("scope_id")
    sub_scope_id = request.args.get("sub_scope_id")
    month = request.args.get("month")

    # ดึงข้อมูล materials
    materials = Material.objects(
        month=int(month_id),
        year=int(year),
        scope=int(scope_id),
        sub_scope=int(sub_scope_id),
        department=current_user.department_key,
        campus=current_user.campus_id,
    )

    # ดึงข้อมูล head_table และ materials_form
    scope = Scope.objects(
        ghg_scope=int(scope_id),
        ghg_sup_scope=int(sub_scope_id),
        department=current_user.department_key,
        campus=current_user.campus_id,
    ).first()
    head_table = scope.head_table if scope else []
    materials_form = []
    for head in head_table:
        form_and_formula = FormAndFormula.objects(material_name=head).first()
        if form_and_formula:
            materials_form.append(form_and_formula.input_types)

    # ส่งข้อมูลไปยังเทมเพลต
    return render_template(
        "emissions-scope/partials/materials-form.html",
        materials=materials,
        materials_form=materials_form,
        head_table=head_table,
        month_id=month_id,
        year=year,
        scope_id=scope_id,
        sub_scope_id=sub_scope_id,
        month=month,
    )


def calculate_result(material, visited_ids=None):
    """
    คำนวณผลลัพธ์จากสูตรและบันทึก result และ result2 ลงใน material
    พร้อมทั้งคำนวณผลลัพธ์ก๊าซทั้ง 7 ชนิด
    รองรับ linked fields โดยดึงข้อมูลจาก Material ของฟอร์มต้นฉบับ
    """
    # Prevent infinite recursion
    if visited_ids is None:
        visited_ids = set()
    
    if str(material.id) in visited_ids:
        return
        
    visited_ids.add(str(material.id))

    # ดึงข้อมูลสูตรจากฐานข้อมูล
    form_and_formula = FormAndFormula.objects(material_name=material.name).first()
    if not form_and_formula:
        return
    
    # ตรวจสอบว่า formula เป็น None หรือ empty string
    if not form_and_formula.formula or form_and_formula.formula.strip() == "":
        return

    # สร้าง mapping ระหว่างชื่อตัวแปรภาษาไทย กับชื่อที่ปลอดภัย
    # Strip whitespace เพราะ variables อาจมี space ท้าย แต่ใน formula ไม่มี
    variable_mapping = {
        original_var.strip(): f"var_{i}"
        for i, original_var in enumerate(form_and_formula.variables)
    }

    sanitized_variables = {}
    for safe_name in variable_mapping.values():
        sanitized_variables[safe_name] = 0

    # ดึงค่าตัวแปรจาก quantity_type (เฉพาะที่อยู่ใน variables)
    for input_type in form_and_formula.input_types:
        if not input_type.is_used:
            continue
        
        # Prepare input_type field for comparison (strip whitespace)
        input_field_clean = input_type.field.strip()
        
        # ดูก่อนว่า material.quantity_type มีข้อมูลของ field นี้หรือไม่
        found_in_quantity_type = False
        for qt in material.quantity_type:
            # เช็คว่า qt.field ต้องตรงกับ input_type.field และอยู่ใน variable_mapping
            # Normalize comparisons by stripping whitespace from both sides
            qt_field_clean = qt.field.strip() if qt.field else ""
            
            # Check if fields match (ignoring whitespace) AND if the field is in our variable mapping
            if qt_field_clean == input_field_clean and input_field_clean in variable_mapping:
                safe_name = variable_mapping[input_field_clean]
                sanitized_variables[safe_name] = qt.amount
                found_in_quantity_type = True
                break
        
        # ถ้าไม่มีใน quantity_type และเป็น linked field ให้ไปดึงจาก source (fallback)
        if not found_in_quantity_type and input_type.source_form_id:
            try:
                from bson import ObjectId
                source_form = FormAndFormula.objects(id=ObjectId(input_type.source_form_id)).first()
                if source_form:
                    source_material = Material.objects(
                        name=source_form.material_name,
                        month=material.month,
                        year=material.year,
                        campus=material.campus,
                        department=material.department
                    ).first()
                    
                    if source_material:
                        for qt in source_material.quantity_type:
                            if qt.field == input_type.original_field:
                                if input_field_clean in variable_mapping:
                                    safe_name = variable_mapping[input_field_clean]
                                    sanitized_variables[safe_name] = qt.amount
                                break
            except Exception as e:
                pass

    sanitized_formula = form_and_formula.formula
    sorted_vars = sorted(variable_mapping.keys(), key=len, reverse=True)

    for original_var in sorted_vars:
        safe_name = variable_mapping[original_var]
        sanitized_formula = re.sub(
            r"\b" + re.escape(original_var) + r"\b", safe_name, sanitized_formula
        )

    try:
        # คำนวณผลลัพธ์แรก (result)
        eval_result = eval(sanitized_formula, {}, sanitized_variables)

        # บันทึกผลลัพธ์ลงใน material.result
        material.result = eval_result

        # คำนวณ result2 ถ้ามี formula2
        if hasattr(form_and_formula, "formula2") and form_and_formula.formula2:
            try:
                # สร้าง variables สำหรับ formula2 ที่รวม result ด้วย
                formula2_variables = sanitized_variables.copy()
                formula2_variables["result"] = eval_result  # เพิ่ม result เข้าไปในตัวแปร

                # ทำ sanitization สำหรับ formula2
                sanitized_formula2 = form_and_formula.formula2

                # แทนที่ตัวแปรใน formula2
                for original_var in sorted_vars:
                    safe_name = variable_mapping[original_var]
                    sanitized_formula2 = re.sub(
                        r"\b" + re.escape(original_var) + r"\b",
                        safe_name,
                        sanitized_formula2,
                    )

                # คำนวณ result2
                eval_result2 = eval(sanitized_formula2, {}, formula2_variables)
                material.result2 = eval_result2

            except Exception as e:
                material.result2 = None
        else:
            # ถ้าไม่มี formula2 ให้ตั้งค่า result2 เป็น None
            material.result2 = None

        # คำนวณผลลัพธ์ก๊าซทั้ง 7 ชนิดโดยใช้ gas_calculation
        try:
            from ..views.gas_calculation import calculate_gas_results

            gas_results = calculate_gas_results(material, form_and_formula)

            # บันทึกผลลัพธ์ก๊าซลงใน material
            material.result_co2 = gas_results.get("result_co2")
            material.result_ch4 = gas_results.get("result_ch4")
            material.result_n2o = gas_results.get("result_n2o")
            material.result_hfcs = gas_results.get("result_hfcs")
            material.result_pfcs = gas_results.get("result_pfcs")
            material.result_sf6 = gas_results.get("result_sf6")
            material.result_nf3 = gas_results.get("result_nf3")

        except Exception as e:
            # ตั้งค่า gas results เป็น None หากคำนวณไม่สำเร็จ
            material.result_co2 = None
            material.result_ch4 = None
            material.result_n2o = None
            material.result_hfcs = None
            material.result_pfcs = None
            material.result_sf6 = None
            material.result_nf3 = None

        material.update_date = datetime.datetime.now()
        material.save()

    except Exception as e:
        pass


def save_material(scope_id, sub_scope_id, month_id, year, material_data):
    """
    Save a single material to the database และคำนวณ result
    """
    head = material_data["head"]
    field = material_data["field"]
    amount = material_data["amount"]
    
    # Initialize visited_ids for this save operation to track recursion
    visited_ids = set()

    # ค้นหา Material ที่ตรงกับข้อมูล
    material = Material.objects(
        month=int(month_id),
        name=head,
        scope=int(scope_id),
        sub_scope=int(sub_scope_id),
        year=year,
        department=current_user.department_key,
        campus=current_user.campus_id,
    ).first()

    # ค้นหา FormAndFormula ที่ตรงกับ head
    form_and_formula = FormAndFormula.objects(material_name=head).first()
    if not form_and_formula:

        return False

    # ค้นหา InputType ที่ตรงกับ field
    input_type = form_and_formula.input_types.filter(field=field).first()
    if not input_type:

        return False

    # อัปเดตหรือสร้าง Material
    if material:
        updated = False
        for qt in material.quantity_type:
            if qt.field == field:
                qt.amount = float(amount)
                updated = True
        if not updated:
            material.quantity_type.append(
                QuantityType(
                    field=field,
                    label=input_type.label,
                    amount=float(amount),
                    unit=input_type.unit,
                )
            )
        material.department = current_user.department_key
        material.campus = current_user.campus_id
        material.edit_by_id = str(current_user.id)
        material.update_date = datetime.datetime.now()
        material.save()
    else:
        new_material = Material(
            month=int(month_id),
            name=head,
            scope=int(scope_id),
            sub_scope=int(sub_scope_id),
            year=year,
            day=1,
            form_and_formula=str(form_and_formula.id),
            department=current_user.department_key,
            campus=current_user.campus_id,
            edit_by_id=str(current_user.id),
            update_date=datetime.datetime.now(),
            quantity_type=[
                QuantityType(
                    field=field,
                    label=input_type.label,
                    amount=float(amount),
                    unit=input_type.unit,
                )
            ],
        )
        new_material.save()
        material = new_material

    # คำนวณและบันทึก result
    calculate_result(material, visited_ids)

    # จัดการ Material ที่ลิงก์ - ใช้ used_by_forms แทนการ query ทุกฟอร์ม
    source_form = FormAndFormula.objects(material_name=head).first()
    if source_form and source_form.used_by_forms:
        # Loop เฉพาะฟอร์มที่ใช้ฟอร์มนี้เท่านั้น (O(1) แทน O(n))
        from bson import ObjectId
        for linked_form_id in source_form.used_by_forms:
            try:
                linked_formula = FormAndFormula.objects(id=ObjectId(linked_form_id)).first()
                if not linked_formula or not linked_formula.is_linked:
                    continue
                    
                linked_material = Material.objects(
                    month=int(month_id),
                    name=linked_formula.material_name,
                    scope=int(linked_formula.ghg_scope),
                    sub_scope=int(linked_formula.ghg_sup_scope),
                    year=year,
                    department=current_user.department_key,
                    campus=current_user.campus_id,
                ).first()

                if linked_material:
                    # เก็บ custom fields เดิมไว้ (ฟิลด์ที่ไม่ได้ลิงก์มาจาก source form นี้)
                    existing_quantity_types = []
                    if linked_material.quantity_type:
                        for qt in linked_material.quantity_type:
                            # เช็คว่า qt.field นี้เป็น linked field จาก source form นี้หรือไม่
                            is_from_this_source = False
                            for input_type in linked_formula.input_types:
                                if (input_type.field == qt.field and 
                                    hasattr(input_type, 'source_form_id') and 
                                    str(input_type.source_form_id) == str(source_form.id)):
                                    is_from_this_source = True
                                    break
                            
                            # ถ้าไม่ใช่ linked field จาก source form นี้ ให้เก็บไว้
                            if not is_from_this_source:
                                existing_quantity_types.append(qt)
                    
                    # อัปเดตเฉพาะ linked fields ที่ source material มีข้อมูลจริง
                    for input_type in linked_formula.input_types:
                        if (hasattr(input_type, 'source_form_id') and 
                            str(input_type.source_form_id) == str(source_form.id) and
                            hasattr(input_type, 'original_field')):
                            
                            # หาค่าจาก source material ตาม original_field
                            source_value = None
                            for qt in material.quantity_type:
                                if qt.field == input_type.original_field:
                                    source_value = qt.amount
                                    break
                            
                            # อัปเดตเฉพาะถ้ามีข้อมูลจริงใน source material
                            if source_value is not None:
                                existing_quantity_types.append(
                                    QuantityType(
                                        field=input_type.field,
                                        label=input_type.label,
                                        amount=float(source_value),
                                        unit=input_type.unit,
                                    )
                                )
                    
                    # บันทึก quantity_types ที่รวม custom fields เดิม + linked field ที่อัปเดต
                    linked_material.quantity_type = existing_quantity_types
                    linked_material.is_linked = True
                    linked_material.edit_by_id = str(current_user.id)
                    linked_material.update_date = datetime.datetime.now()
                    linked_material.save()

                    # คำนวณ result ใหม่ตามสูตรของ linked material
                    calculate_result(linked_material, visited_ids)
                else:
                    # สร้าง material ใหม่ - รวมเฉพาะ linked fields ที่ source มีข้อมูลจริง
                    linked_quantity_types = []
                    for input_type in linked_formula.input_types:
                        if (hasattr(input_type, 'source_form_id') and 
                            str(input_type.source_form_id) == str(source_form.id) and
                            hasattr(input_type, 'original_field')):
                            
                            # หาค่าจาก source material ตาม original_field
                            source_value = None
                            for qt in material.quantity_type:
                                if qt.field == input_type.original_field:
                                    source_value = qt.amount
                                    break
                            
                            # เพิ่มเฉพาะถ้ามีข้อมูลจริงใน source material
                            if source_value is not None:
                                linked_quantity_types.append(
                                    QuantityType(
                                        field=input_type.field,
                                        label=input_type.label,
                                        amount=float(source_value),
                                        unit=input_type.unit,
                                    )
                                )
                    
                    linked_material = Material(
                        month=int(month_id),
                        name=linked_formula.material_name,
                        scope=int(linked_formula.ghg_scope),
                        sub_scope=int(linked_formula.ghg_sup_scope),
                        year=year,
                        day=1,
                        form_and_formula=str(linked_formula.id),
                        department=current_user.department_key,
                        campus=current_user.campus_id,
                        edit_by_id=str(current_user.id),
                        update_date=datetime.datetime.now(),
                        quantity_type=linked_quantity_types,
                        is_linked=True,
                    )
                    linked_material.save()

                    # คำนวณ result ตามสูตรของ linked material
                    calculate_result(linked_material, visited_ids)
            except Exception as e:
                print(f"Error updating linked material for form {linked_form_id}: {e}")
                continue

    return True


@module.route("/save-materials", methods=["POST"])
@login_required
# @permissions_required_all(["เซฟข้อมูลการปล่อย"])
def save_materials():
    scope_id = request.form.get("scope_id")
    sub_scope_id = request.form.get("sub_scope_id")
    month_id = request.form.get("month_id")
    year = request.form.get("year")
    page = int(request.form.get("page", 1))  # รับค่าหน้าปัจจุบัน
    input_label = request.form.get("input_label")
    input_field = request.form.get("input_field")
    quick_edit_mode = request.form.get("quick_edit_mode", "false").lower() == "true"

    # Flask-WTF validation (minimal impact - same error handling as before)
    # ✅ กำหนด validation mode ให้ถูกต้อง
    if quick_edit_mode:
        validation_mode = "quick_edit"
    elif "head" in request.form and "amount" in request.form:
        validation_mode = "single"  # โหมดปกติ (material-form.html)
    else:
        validation_mode = "multiple"  # โหมดหลายตัว (materials-form.html)

    is_valid, validation_errors = validate_material_data(
        dict(request.form), validation_mode
    )

    if not is_valid:
        # Add debug logging for troubleshooting
        print(f"Validation failed: {validation_errors}")
        print(f"Form data keys: {list(request.form.keys())}")
        print(f"Validation mode: {validation_mode}")
        print(
            f"Amount fields: {[k for k in request.form.keys() if k.startswith('amount_')]}"
        )

        # Return validation errors via existing toast notification system
        response = make_response("")
        error_message = "; ".join(validation_errors[:3])  # Show first 3 errors
        if len(validation_errors) > 3:
            error_message += f"... และอีก {len(validation_errors) - 3} ข้อผิดพลาด"

        encoded_message = urllib.parse.quote(error_message)
        trigger_data = {"showError": encoded_message}
        response.headers["HX-Trigger"] = json.dumps(trigger_data)
        return response

    # Debug information for save_materials
    # print(f"=== SAVE MATERIALS DEBUG ===")
    # print(f"Request form keys: {list(request.form.keys())}")
    # print(f"Quick edit mode: {quick_edit_mode}")
    # print(f"Scope: {scope_id}, Sub scope: {sub_scope_id}")
    # print(f"Year: {year}, Page: {page}")

    # Show form data related to amounts
    amount_keys = [key for key in request.form.keys() if key.startswith("amount_")]
    # print(f"Amount keys found: {len(amount_keys)}")
    # for key in amount_keys[:5]:  # Show first 5 for debugging
    # print(f"  {key}: {request.form.get(key)}")
    # print(f"=============================")

    # ตรวจสอบว่า scope และ sub_scope มีอยู่ในฐานข้อมูล
    scope = Scope.objects(
        ghg_scope=int(scope_id),
        ghg_sup_scope=int(sub_scope_id),
        department=current_user.department_key,
        campus=current_user.campus_id,
    ).first()

    if not scope:

        # ใช้ toast notification สำหรับ error

        response = make_response("")
        encoded_message = urllib.parse.quote("ไม่พบข้อมูล Scope ที่ระบุ")

        trigger_data = {"showError": encoded_message}
        response.headers["HX-Trigger"] = json.dumps(trigger_data)
        return response

    head_table = scope.head_table

    # Extract materials from form
    materials = []
    if "head" in request.form and "amount" in request.form:
        # Single material case (from material-form.html)
        head = request.form.get("head")
        amount = request.form.get("amount")

        form_and_formula = FormAndFormula.objects(material_name=head).first()
        if not form_and_formula:

            # ใช้ toast notification สำหรับ error
            response = make_response("")
            encoded_message = urllib.parse.quote("ไม่พบฟอร์มสำหรับวัสดุที่ระบุ")

            trigger_data = {"showError": encoded_message}
            response.headers["HX-Trigger"] = json.dumps(trigger_data)
            return response

        field = input_field
        if not field:

            # ใช้ toast notification สำหรับ error
            response = make_response("")
            encoded_message = urllib.parse.quote("ไม่พบฟิลด์ข้อมูลสำหรับวัสดุที่ระบุ")

            trigger_data = {"showError": encoded_message}
            response.headers["HX-Trigger"] = json.dumps(trigger_data)
            return response

        materials.append({"head": head, "field": field, "amount": amount})
    elif quick_edit_mode:
        # Quick edit mode: handle multiple months and materials
        # Only save data that has actually changed
        # print("Processing quick edit mode data...")

        # Get all current materials for comparison
        current_materials = Material.objects(
            scope=int(scope_id),
            sub_scope=int(sub_scope_id),
            year=int(year),
            department=current_user.department_key,
            campus=current_user.campus_id,
        )

        # Create a lookup for existing data
        existing_data = {}
        for material in current_materials:
            for qt in material.quantity_type:
                key = f"{material.month}_{material.name}_{qt.field}"
                existing_data[key] = str(qt.amount) if qt.amount else ""

        # print(f"Found {len(existing_data)} existing data entries")

        for key in request.form.keys():
            if key.startswith("amount_"):
                # Parse field name: amount_{month_id}_{head}_{field}
                parts = key.replace("amount_", "").split("_", 2)
                if len(parts) == 3:
                    month_id_temp, head, field = parts
                    new_amount = request.form.get(key, "").strip()

                    # Create lookup key for existing data
                    lookup_key = f"{month_id_temp}_{head}_{field}"
                    existing_amount = existing_data.get(lookup_key, "")

                    # Check if value has changed (including deletion - empty to non-empty or vice versa)
                    if new_amount != existing_amount:
                        # print(
                        # f"Value changed for {lookup_key}: '{existing_amount}' -> '{new_amount}'"
                        # )

                        if new_amount:  # New value provided
                            materials.append(
                                {
                                    "head": head,
                                    "field": field,
                                    "amount": new_amount,
                                    "month_id": month_id_temp,
                                }
                            )
                        elif (
                            existing_amount
                        ):  # Existing value should be deleted (user cleared the field)
                            # Add to deletion list - we'll handle this separately
                            materials.append(
                                {
                                    "head": head,
                                    "field": field,
                                    "amount": "",  # Empty means delete
                                    "month_id": month_id_temp,
                                    "delete": True,  # Flag for deletion
                                }
                            )
                    # else:
                    # print(f"No change for {lookup_key}: '{existing_amount}'")

        # print(f"Total changed materials to save: {len(materials)}")
    else:
        # Multiple materials case (from materials-form.html)
        for key in request.form.keys():
            if key.startswith("amount_"):
                parts = key.split("_")
                if len(parts) < 3:

                    continue
                head = parts[1]
                field = parts[2]
                amount = request.form.get(key)

                # เพิ่มเงื่อนไขตรวจสอบ amount ก่อน append
                if amount and amount.strip():  # เซฟเฉพาะฟิลด์ที่มีการกรอกข้อมูล
                    materials.append({"head": head, "field": field, "amount": amount})

    # Debugging: Print materials data

    # Check required parameters based on mode
    if quick_edit_mode:
        # In quick edit mode, we don't need month_id as a single parameter
        if not scope_id or not sub_scope_id or not year:
            # print(
            # f"Missing required parameters in quick edit mode: scope_id={scope_id}, sub_scope_id={sub_scope_id}, year={year}"
            # )
            # ใช้ toast notification สำหรับ error
            response = make_response("")
            encoded_message = urllib.parse.quote("ข้อมูลไม่ครบถ้วน กรุณาตรวจสอบอีกครั้ง")

            trigger_data = {"showError": encoded_message}
            response.headers["HX-Trigger"] = json.dumps(trigger_data)
            return response
    else:
        # In normal mode, we need all parameters including month_id
        if not scope_id or not sub_scope_id or not month_id or not year:
            # print(
            # f"Missing required parameters in normal mode: scope_id={scope_id}, sub_scope_id={sub_scope_id}, month_id={month_id}, year={year}"
            # )
            # ใช้ toast notification สำหรับ error
            response = make_response("")
            encoded_message = urllib.parse.quote("ข้อมูลไม่ครบถ้วน กรุณาตรวจสอบอีกครั้ง")

            trigger_data = {"showError": encoded_message}
            response.headers["HX-Trigger"] = json.dumps(trigger_data)
            return response

    if not materials:
        # ใช้ toast notification สำหรับ warning
        response = make_response("")
        encoded_message = urllib.parse.quote("กรุณากรอกข้อมูลอย่างน้อย 1 ฟิลด์")

        trigger_data = {"showWarning": encoded_message}
        response.headers["HX-Trigger"] = json.dumps(trigger_data)
        return response

    # Save each material
    saved_count = 0
    deleted_count = 0

    for material_data in materials:
        # Get month_id for this specific material (for quick edit mode)
        material_month_id = material_data.get("month_id", month_id)

        # ตรวจสอบว่า field นี้เป็น linked field หรือไม่
        form_and_formula = FormAndFormula.objects(material_name=material_data["head"]).first()
        if form_and_formula:
            input_type = form_and_formula.input_types.filter(field=material_data["field"]).first()
            # ถ้าฟิลด์นี้มี source_form_id แสดงว่าเป็น linked field ไม่ให้แก้ไข
            if input_type and hasattr(input_type, 'source_form_id') and input_type.source_form_id:
                continue  # ข้าม linked field (อ่านได้อย่างเดียว)

        # Handle deletion vs save
        if material_data.get("delete", False):
            # Delete the specific field
            if delete_material_and_linked(
                scope_id,
                sub_scope_id,
                material_month_id,
                year,
                material_data["head"],
                material_data["field"],
            ):
                deleted_count += 1
                # print(
                # f"Deleted field {material_data['field']} for {material_data['head']}"
                # )
        else:
            # Save/update the material
            if save_material(
                scope_id, sub_scope_id, material_month_id, year, material_data
            ):
                saved_count += 1

    # print(f"Operation completed: {saved_count} saved, {deleted_count} deleted")

    # Update emissions table
    head_table = scope.head_table  # Re-fetch head_table after saving materials

    current_headers, materials_form, total_pages, items_per_page = (
        calculate_grouped_input_types(head_table, page)
    )

    # สร้าง head_table_info สำหรับ current_headers (Optimized)
    forms_info = FormAndFormula.objects(material_name__in=current_headers)
    form_map_info = {f.material_name: f for f in forms_info}
    
    head_table_info = {}
    for head in current_headers:
        form = form_map_info.get(head)
        if form:
            head_table_info[head] = {
                "is_linked": getattr(form, "is_linked", False),
                "linked_forms": getattr(form, "linked_forms", []),
                "desc_form": form.desc_form,
                "formula": form.formula,
            }

    # สร้าง materials_form ใหม่ตาม current_headers (Optimized)
    materials_form = []
    # reuse form_map_info from above
    for head in current_headers:
        form_and_formula = form_map_info.get(head)
        if form_and_formula:
            materials_form.append(form_and_formula.input_types)

    # กรองข้อมูล Material ตามปีที่เลือก (รีเฟรชหลังบันทึก)
    materials = Material.objects(
        scope=int(scope_id),
        sub_scope=int(sub_scope_id),
        year=int(year),
        department=current_user.department_key,
        campus=current_user.campus_id,
    )

    # Get all available scopes for user
    user_scopes = get_user_scopes()

    # Find current scope index for navigation
    current_scope_index = get_current_scope_index(
        user_scopes, int(scope_id), int(sub_scope_id)
    )

    if request.headers.get("HX-Request"):
        # Choose template based on edit mode
        template_name = (
            "emissions-scope/partials/quick-edit-table.html"
            if quick_edit_mode
            else "emissions-scope/partials/emissions-table.html"
        )

        # สร้าง response พร้อม toast notification
        table_html = render_template(
            template_name,
            scope=scope,
            scope_id=scope_id,
            sub_scope_id=sub_scope_id,
            materials=materials,
            head_table=current_headers,
            head_table_info=head_table_info,  # เพิ่มบรรทัดนี้
            total_pages=total_pages,
            page=page,  # ส่งหน้าปัจจุบันกลับไปยังเทมเพลต
            user=current_user,
            year=year,
            materials_form=materials_form,
            items_per_page=items_per_page,  # ส่งจำนวนรายการต่อหน้า
            user_scopes=user_scopes,
            current_scope_index=current_scope_index,
        )

        response = make_response(table_html)

        # เพิ่ม toast notification สำหรับความสำเร็จ
        if saved_count > 0:
            encoded_message = urllib.parse.quote(f"บันทึกข้อมูลสำเร็จ!")
            trigger_data = {"showSuccess": encoded_message}
            response.headers["HX-Trigger"] = json.dumps(trigger_data)

        return response
    else:
        return redirect(
            url_for(
                "emissions.view_emissions",
                scope_id=scope_id,
                sub_scope_id=sub_scope_id,
                year=year,
            )
        )


def delete_material_and_linked(
    scope_id, sub_scope_id, month_id, year, head, input_field
):
    """
    Delete a single material field and update linked materials
    """
    # ลบข้อมูลหลัก
    material = Material.objects(
        month=int(month_id),
        name=head,
        scope=int(scope_id),
        sub_scope=int(sub_scope_id),
        year=int(year),
        department=current_user.department_key,
        campus=current_user.campus_id,
    ).first()

    if material:
        # ลบฟิลด์ที่ระบุ
        material.quantity_type = [
            qt for qt in material.quantity_type if qt.field != input_field
        ]
        material.edit_by_id = str(current_user.id)
        material.update_date = datetime.datetime.now()
        material.save()

        # คำนวณ result ใหม่
        calculate_result(material)

        # จัดการ Material ที่ลิงก์ - ใช้ used_by_forms แทนการ query ทุกฟอร์ม
        source_form = FormAndFormula.objects(material_name=head).first()
        if source_form and source_form.used_by_forms:
            from bson import ObjectId
            for linked_form_id in source_form.used_by_forms:
                try:
                    linked_formula = FormAndFormula.objects(id=ObjectId(linked_form_id)).first()
                    if not linked_formula or not linked_formula.is_linked:
                        continue
                        
                    linked_material = Material.objects(
                        month=int(month_id),
                        name=linked_formula.material_name,
                        scope=int(linked_formula.ghg_scope),
                        sub_scope=int(linked_formula.ghg_sup_scope),
                        year=int(year),
                        department=current_user.department_key,
                        campus=current_user.campus_id,
                    ).first()

                    if linked_material:
                        # ตรวจสอบว่า material ต้นฉบับยังมีข้อมูลอยู่หรือไม่
                        if material.quantity_type and material.result is not None:
                            # ถ้ายังมีข้อมูล ให้อัปเดต linked material ด้วยค่าใหม่
                            linked_quantity_types = []
                            if linked_formula.input_types:
                                first_input = linked_formula.input_types[0]
                                linked_quantity_types = [
                                    QuantityType(
                                        field=first_input.field,
                                        label=first_input.label,
                                        amount=float(material.result),
                                        unit=first_input.unit,
                                    )
                                ]

                            linked_material.quantity_type = linked_quantity_types
                            linked_material.is_linked = True
                            linked_material.edit_by_id = str(current_user.id)
                            linked_material.update_date = datetime.datetime.now()
                            linked_material.save()

                            # คำนวณ result ใหม่
                            calculate_result(linked_material)
                        else:
                            # ถ้าไม่มีข้อมูลแล้ว ให้ลบ linked material ออกเลย หรือทำให้เป็นค่าว่าง
                            linked_material.quantity_type = []
                            linked_material.result = None
                            linked_material.result2 = None
                            linked_material.result_co2 = None
                            linked_material.result_ch4 = None
                            linked_material.result_n2o = None
                            linked_material.result_hfcs = None
                            linked_material.result_pfcs = None
                            linked_material.result_sf6 = None
                            linked_material.result_nf3 = None
                            linked_material.edit_by_id = str(current_user.id)
                            linked_material.update_date = datetime.datetime.now()
                            linked_material.save()
                except Exception as e:
                    print(f"Error updating linked material for form {linked_form_id}: {e}")
                    continue

    return True


@module.route("/delete-material", methods=["POST"])
@login_required
# @permissions_required_all(["ลบข้อมูลการปล่อย"])
def delete_material():
    scope_id = request.form.get("scope_id")
    sub_scope_id = request.form.get("sub_scope_id")
    month_id = request.form.get("month_id")
    year = request.form.get("year")
    head = request.form.get("head")
    input_field = request.form.get("input_field")
    page = int(request.form.get("page", 1))

    # ใช้ฟังก์ชันใหม่ที่จัดการ linked materials
    delete_material_and_linked(
        scope_id, sub_scope_id, month_id, year, head, input_field
    )

    # Refresh table after deletion
    scope = Scope.objects(
        ghg_scope=int(scope_id),
        ghg_sup_scope=int(sub_scope_id),
        department=current_user.department_key,
        campus=current_user.campus_id,
    ).first()
    head_table = scope.head_table if scope else []

    current_headers, materials_form, total_pages, items_per_page = (
        calculate_grouped_input_types(head_table, page)
    )

    # สร้าง head_table_info สำหรับ current_headers
    head_table_info = {}
    for head in current_headers:
        form = FormAndFormula.objects(material_name=head).first()
        if form:
            head_table_info[head] = {
                "is_linked": getattr(form, "is_linked", False),
                "linked_forms": getattr(form, "linked_forms", []),
                "desc_form": form.desc_form,
                "formula": form.formula,
            }

    # Get all available scopes for user
    user_scopes = get_user_scopes()

    # Find current scope index for navigation
    current_scope_index = get_current_scope_index(
        user_scopes, int(scope_id), int(sub_scope_id)
    )

    materials = Material.objects(
        scope=int(scope_id),
        sub_scope=int(sub_scope_id),
        year=int(year),
        department=current_user.department_key,
        campus=current_user.campus_id,
    )

    if request.headers.get("HX-Request"):
        # สร้าง response พร้อม toast notification สีเหลือง
        table_html = render_template(
            "emissions-scope/partials/emissions-table.html",
            scope=scope,
            scope_id=scope_id,
            sub_scope_id=sub_scope_id,
            materials=materials,
            head_table=current_headers,
            head_table_info=head_table_info,
            total_pages=total_pages,
            page=page,
            user=current_user,
            year=year,
            materials_form=materials_form,
            items_per_page=items_per_page,
            user_scopes=user_scopes,
            current_scope_index=current_scope_index,
        )

        response = make_response(table_html)

        # เพิ่ม toast notification สีเหลืองสำหรับการลบ
        encoded_message = urllib.parse.quote("ลบข้อมูลเรียบร้อยแล้ว")

        trigger_data = {"showWarning": encoded_message}
        response.headers["HX-Trigger"] = json.dumps(trigger_data)

        return response


@module.route("/delete-all-materials", methods=["POST"])
@login_required
# @permissions_required_all(["ลบข้อมูลการปล่อยกทั้งหมด"])
def delete_all_materials():
    scope_id = request.form.get("scope_id")
    sub_scope_id = request.form.get("sub_scope_id")
    month_id = request.form.get("month_id")
    year = request.form.get("year")
    page = int(request.form.get("page", 1))

    try:
        materials = Material.objects(
            month=int(month_id),
            scope=int(scope_id),
            sub_scope=int(sub_scope_id),
            year=int(year),
            department=current_user.department_key,
            campus=current_user.campus_id,
        )

        deleted_count = 0
        if materials:
            # รวบรวมรายชื่อ materials ที่ต้องอัปเดต linked materials
            materials_to_update_linked = []

            for material in materials:
                if material.is_linked:
                    continue  # ข้าม material ที่ถูกลิงก์

                # นับจำนวน quantity_type ที่มีอยู่ก่อนลบ
                quantity_count_before_delete = (
                    len(material.quantity_type) if material.quantity_type else 0
                )
                deleted_count += quantity_count_before_delete

                # เก็บชื่อ material สำหรับอัปเดต linked materials ภายหลัง
                if material.name and quantity_count_before_delete > 0:
                    materials_to_update_linked.append(material.name)

                material.quantity_type = []  # Clear quantity_type
                material.result = None
                material.result2 = None
                material.result_co2 = None
                material.result_ch4 = None
                material.result_n2o = None
                material.result_hfcs = None
                material.result_pfcs = None
                material.result_sf6 = None
                material.result_nf3 = None
                material.edit_by_id = str(current_user.id)
                material.update_date = datetime.datetime.now()
                material.save()

            # อัปเดต linked materials สำหรับทุก material ที่ถูกลบ - ใช้ used_by_forms
            for material_name in materials_to_update_linked:
                source_form = FormAndFormula.objects(material_name=material_name).first()
                if source_form and source_form.used_by_forms:
                    from bson import ObjectId
                    for linked_form_id in source_form.used_by_forms:
                        try:
                            linked_formula = FormAndFormula.objects(id=ObjectId(linked_form_id)).first()
                            if not linked_formula or not linked_formula.is_linked:
                                continue
                                
                            linked_material = Material.objects(
                                month=int(month_id),
                                name=linked_formula.material_name,
                                scope=int(linked_formula.ghg_scope),
                                sub_scope=int(linked_formula.ghg_sup_scope),
                                year=int(year),
                                department=current_user.department_key,
                                campus=current_user.campus_id,
                            ).first()

                            if linked_material:
                                # เนื่องจากลบข้อมูลทั้งหมดแล้ว ให้ทำให้ linked material เป็นค่าว่างทุกอย่าง
                                linked_material.quantity_type = []
                                linked_material.result = None
                                linked_material.result2 = None
                                linked_material.result_co2 = None
                                linked_material.result_ch4 = None
                                linked_material.result_n2o = None
                                linked_material.result_hfcs = None
                                linked_material.result_pfcs = None
                                linked_material.result_sf6 = None
                                linked_material.result_nf3 = None
                                linked_material.edit_by_id = str(current_user.id)
                                linked_material.update_date = datetime.datetime.now()
                                linked_material.save()
                        except Exception as e:
                            print(f"Error clearing linked material for form {linked_form_id}: {e}")
                            continue

        # Refresh table after deletion
        scope = Scope.objects(
            ghg_scope=int(scope_id),
            ghg_sup_scope=int(sub_scope_id),
            department=current_user.department_key,
            campus=current_user.campus_id,
        ).first()
        head_table = scope.head_table if scope else []

        current_headers, materials_form, total_pages, items_per_page = (
            calculate_grouped_input_types(head_table, page)
        )

        # สร้าง head_table_info สำหรับ current_headers (Optimized)
        forms_info = FormAndFormula.objects(material_name__in=current_headers)
        form_map_info = {f.material_name: f for f in forms_info}

        head_table_info = {}
        for head in current_headers:
            form = form_map_info.get(head)
            if form:
                head_table_info[head] = {
                    "is_linked": getattr(form, "is_linked", False),
                    "linked_forms": getattr(form, "linked_forms", []),
                    "desc_form": form.desc_form,
                    "formula": form.formula,
                }

        materials = Material.objects(
            scope=int(scope_id),
            sub_scope=int(sub_scope_id),
            year=int(year),
            department=current_user.department_key,
            campus=current_user.campus_id,
        )

        # Get all available scopes for user
        user_scopes = get_user_scopes()

        # Find current scope index for navigation
        current_scope_index = get_current_scope_index(
            user_scopes, int(scope_id), int(sub_scope_id)
        )

        if request.headers.get("HX-Request"):
            # สร้าง response พร้อม toast notification
            table_html = render_template(
                "emissions-scope/partials/emissions-table.html",
                scope=scope,
                scope_id=scope_id,
                sub_scope_id=sub_scope_id,
                materials=materials,
                head_table=current_headers,
                head_table_info=head_table_info,
                total_pages=total_pages,
                page=page,
                user=current_user,
                year=year,
                materials_form=materials_form,
                items_per_page=items_per_page,
                user_scopes=user_scopes,
                current_scope_index=current_scope_index,
            )

            response = make_response(table_html)

            # เปลี่ยนเป็น toast notification สีเหลืองสำหรับการลบ
            if deleted_count > 0:
                # แสดง warning toast สีเหลืองแทนสีเขียว
                encoded_message = urllib.parse.quote(
                    f"ลบข้อมูลทั้งหมดเรียบร้อยแล้ว ({deleted_count} รายการ)"
                )
                trigger_data = {"showWarning": encoded_message}
            else:
                # แสดง info toast ถ้าไม่มีการลบ
                encoded_message = urllib.parse.quote("ไม่มีข้อมูลที่สามารถลบได้")
                trigger_data = {"showInfo": encoded_message}

            response.headers["HX-Trigger"] = json.dumps(trigger_data)

            return response

    except Exception as e:
        # ใช้ toast notification สำหรับ error
        response = make_response("")
        encoded_message = urllib.parse.quote(f"เกิดข้อผิดพลาดในการลบข้อมูล: {str(e)}")

        trigger_data = {"showError": encoded_message}
        response.headers["HX-Trigger"] = json.dumps(trigger_data)
        return response


@module.route("/load-upload-modal", methods=["GET"])
@login_required
def load_upload_modal(
    month_id=None, year=None, scope_id=None, sub_scope_id=None, month=None
):
    # หากค่าพารามิเตอร์ไม่ได้ถูกส่งมา ให้ดึงค่าจาก request.args
    month_id = month_id or request.args.get("month_id")
    year = year or request.args.get("year")
    scope_id = scope_id or request.args.get("scope_id")
    sub_scope_id = sub_scope_id or request.args.get("sub_scope_id")
    month = month or request.args.get("month")

    # ตรวจสอบค่าที่ได้รับ

    # ตรวจสอบว่าค่าพารามิเตอร์ไม่เป็น None
    if not all([month_id, year, scope_id, sub_scope_id]):
        return jsonify({"error": "Missing required parameters"}), 400

    documents = ReferenceDocument.objects(
        scope_id=int(scope_id),
        sub_scope_id=int(sub_scope_id),
        year=int(year),
        month=int(month_id),
        campus=current_user.campus_id,
        department=current_user.department_key,
    ).first()

    if not documents:
        documents = ReferenceDocument(
            scope_id=int(scope_id),
            sub_scope_id=int(sub_scope_id),
            year=int(year),
            month=int(month_id),
            campus=current_user.campus_id,
            department=current_user.department_key,
            files=[],
        )
        documents.save()

    return render_template(
        "emissions-scope/partials/upload-modal.html",
        documents=documents,
        month_id=month_id,
        year=year,
        scope_id=scope_id,
        sub_scope_id=sub_scope_id,
        month=month,
    )


@module.route("/upload-file", methods=["POST"])
@login_required
# @permissions_required_all(["อัปโหลดไฟล์ข้อมูลการปล่อย"])
def upload_file():
    file = request.files.get("file")
    if not file:
        # ใช้ toast notification สำหรับ error

        response = make_response("")
        encoded_message = urllib.parse.quote("กรุณาเลือกไฟล์ที่ต้องการอัปโหลด")

        trigger_data = {"showError": encoded_message}
        response.headers["HX-Trigger"] = json.dumps(trigger_data)
        return response

    scope_id = request.form.get("scope_id")
    sub_scope_id = request.form.get("sub_scope_id")
    year = request.form.get("year")
    month_id = request.form.get("month_id")
    month = request.form.get("month")  # เพิ่มการดึงค่า month

    # ตรวจสอบว่าค่าพารามิเตอร์ไม่เป็น None
    if not all([scope_id, sub_scope_id, year, month_id]):
        # ใช้ toast notification สำหรับ error
        response = make_response("")
        encoded_message = urllib.parse.quote("ข้อมูลไม่ครบถ้วน กรุณาลองใหม่อีกครั้ง")

        trigger_data = {"showError": encoded_message}
        response.headers["HX-Trigger"] = json.dumps(trigger_data)
        return response

    try:
        document = ReferenceDocument.objects(
            scope_id=int(scope_id),
            sub_scope_id=int(sub_scope_id),
            year=int(year),
            month=int(month_id),
            campus=current_user.campus_id,
            department=current_user.department_key,
        ).first()

        if not document:
            document = ReferenceDocument(
                scope_id=int(scope_id),
                sub_scope_id=int(sub_scope_id),
                year=int(year),
                month=int(month_id),
                campus=current_user.campus_id,
                department=current_user.department_key,
                files=[],
            )

        document.files.append(
            UploadedFile(
                filename=file.filename,
                content_type=file.content_type,
                data=file.read(),
            )
        )
        document.save()

        # สร้าง response พร้อม toast notification สำเร็จ
        modal_html = render_template(
            "emissions-scope/partials/upload-modal.html",
            documents=document,
            month_id=month_id,
            year=year,
            scope_id=scope_id,
            sub_scope_id=sub_scope_id,
            month=month,
        )

        response = make_response(modal_html)
        encoded_message = urllib.parse.quote(f"อัปโหลดไฟล์ '{file.filename}' สำเร็จ!")

        trigger_data = {"showSuccess": encoded_message}
        response.headers["HX-Trigger"] = json.dumps(trigger_data)

        return response

    except Exception as e:
        # ใช้ toast notification สำหรับ error
        response = make_response("")
        encoded_message = urllib.parse.quote(f"เกิดข้อผิดพลาดในการอัปโหลด: {str(e)}")

        trigger_data = {"showError": encoded_message}
        response.headers["HX-Trigger"] = json.dumps(trigger_data)
        return response


@module.route("/download-file/<file_id>", methods=["GET"])
@login_required
# @permissions_required_all(["โหลดข้อมูลการปล่อย"])
def download_file(file_id):
    document = ReferenceDocument.objects(files__id=file_id).first()

    if not document:
        return jsonify({"error": "File not found"}), 404

    file = next((f for f in document.files if str(f.id) == file_id), None)
    if not file:
        return jsonify({"error": "File not found"}), 404

    # เข้ารหัสชื่อไฟล์เป็น UTF-8
    encoded_filename = quote(file.filename)

    response = make_response(file.data)
    response.headers["Content-Type"] = file.content_type
    response.headers["Content-Disposition"] = (
        f"attachment; filename*=UTF-8''{encoded_filename}"
    )
    return response


@module.route("/delete-file/<file_id>", methods=["POST"])
@login_required
# @permissions_required_all(["ลบไฟล์ข้อมูลการปล่อย"])
def delete_file(file_id):

    scope_id = request.form.get("scope_id")
    sub_scope_id = request.form.get("sub_scope_id")
    year = request.form.get("year")
    month_id = request.form.get("month_id")
    month = request.form.get("month")  # เพิ่มการดึงค่า month

    if not file_id:

        # ใช้ toast notification สำหรับ error

        response = make_response("")
        encoded_message = urllib.parse.quote("ไม่พบรหัสไฟล์ที่ต้องการลบ")

        trigger_data = {"showError": encoded_message}
        response.headers["HX-Trigger"] = json.dumps(trigger_data)
        return response

    try:
        document = ReferenceDocument.objects(files__id=file_id).first()
        if not document:

            # ใช้ toast notification สำหรับ error
            response = make_response("")
            encoded_message = urllib.parse.quote("ไม่พบไฟล์ที่ต้องการลบ")

            trigger_data = {"showError": encoded_message}
            response.headers["HX-Trigger"] = json.dumps(trigger_data)
            return response

        # หาชื่อไฟล์ก่อนลบเพื่อแสดงใน toast
        file_to_delete = next((f for f in document.files if str(f.id) == file_id), None)
        filename = file_to_delete.filename if file_to_delete else "ไฟล์"

        document.files = [f for f in document.files if str(f.id) != file_id]
        document.save()

        # สร้าง response พร้อม toast notification สีเหลืองสำหรับการลบไฟล์
        modal_html = render_template(
            "emissions-scope/partials/upload-modal.html",
            documents=document,
            month_id=month_id,
            year=year,
            scope_id=scope_id,
            sub_scope_id=sub_scope_id,
            month=month,
        )

        response = make_response(modal_html)
        encoded_message = urllib.parse.quote(f"ลบไฟล์ '{filename}' เรียบร้อยแล้ว")

        trigger_data = {"showWarning": encoded_message}
        response.headers["HX-Trigger"] = json.dumps(trigger_data)

        return response

    except Exception as e:
        # ใช้ toast notification สำหรับ error
        response = make_response("")
        encoded_message = urllib.parse.quote(f"เกิดข้อผิดพลาดในการลบไฟล์: {str(e)}")

        trigger_data = {"showError": encoded_message}
        response.headers["HX-Trigger"] = json.dumps(trigger_data)
        return response


@module.route("/get-form-details/<material_name>", methods=["GET"])
@login_required
def get_form_details(material_name):
    """
    ดึงรายละเอียดของฟอร์ม รวมถึงข้อมูลการลิงก์
    """
    try:
        form = FormAndFormula.objects(material_name=material_name).first()
        if not form:
            return render_template(
                "emissions-scope/partials/form-detail-modal.html",
                error="ไม่พบฟอร์มที่ต้องการ",
            )

        # ดึงข้อมูล scope
        scope_info = None
        if hasattr(form, "ghg_scope") and hasattr(form, "ghg_sup_scope"):
            scope = Scope.objects(
                ghg_scope=form.ghg_scope, ghg_sup_scope=form.ghg_sup_scope
            ).first()
            if scope:
                scope_info = {
                    "ghg_scope": form.ghg_scope,
                    "ghg_sup_scope": form.ghg_sup_scope,
                    "ghg_name": scope.ghg_name,
                }

        # ดึงข้อมูลฟอร์มต้นทาง (ถ้าเป็นฟอร์มลิงก์)
        source_forms = []
        if getattr(form, "is_linked", False) and getattr(form, "linked_forms", []):
            # ดึงข้อมูลทุกฟอร์มที่ลิงก์
            from bson import ObjectId
            for form_id in form.linked_forms:
                try:
                    source_form = FormAndFormula.objects(id=ObjectId(form_id)).first()
                    if source_form:
                        source_scope = Scope.objects(
                            ghg_scope=source_form.ghg_scope,
                            ghg_sup_scope=source_form.ghg_sup_scope,
                        ).first()
                        
                        source_forms.append({
                            "form": source_form,
                            "scope": source_scope,
                            "scope_name": source_scope.ghg_name if source_scope else "Unknown"
                        })
                except:
                    continue

        # ดึงรายชื่อฟอร์มที่ลิงก์มาจากฟอร์มนี้
        linked_forms = []
        if not getattr(form, "is_linked", False):
            # หาฟอร์มที่มี form ID นี้อยู่ใน linked_forms array
            linked_forms_query = FormAndFormula.objects(
                linked_forms=str(form.id),
                is_linked=True
            )

            for linked_form in linked_forms_query:
                linked_scope = Scope.objects(
                    ghg_scope=linked_form.ghg_scope,
                    ghg_sup_scope=linked_form.ghg_sup_scope,
                ).first()

                linked_forms.append(
                    {
                        "material_name": linked_form.material_name,
                        "desc_form": linked_form.desc_form,
                        "ghg_scope": linked_form.ghg_scope,
                        "ghg_sup_scope": linked_form.ghg_sup_scope,
                        "scope_name": (
                            linked_scope.ghg_name if linked_scope else "Unknown"
                        ),
                    }
                )

        # เพิ่มข้อมูลต้นฉบับของแต่ละฟิลด์
        from bson import ObjectId
        fields_with_source = []
        for input_type in form.input_types:
            field_info = {
                "field": input_type.field,
                "label": input_type.label,
                "input_type": input_type.input_type,
                "unit": input_type.unit,
                "is_used": getattr(input_type, "is_used", True),
                "source_form_name": None,
                "is_linked_field": False,
                "original_field": None
            }
            
            # ตรวจสอบว่าเป็น linked field หรือไม่
            if hasattr(input_type, "source_form_id") and input_type.source_form_id:
                try:
                    source_form = FormAndFormula.objects(id=ObjectId(input_type.source_form_id)).first()
                    if source_form:
                        field_info["source_form_name"] = source_form.material_name
                        field_info["is_linked_field"] = True
                        field_info["original_field"] = getattr(input_type, "original_field", None)
                except Exception as e:
                    pass
            
            fields_with_source.append(field_info)

        return render_template(
            "emissions-scope/partials/form-detail-modal.html",
            form=form,
            scope_info=scope_info,
            source_forms=source_forms,  # เปลี่ยนเป็น list
            linked_forms=linked_forms,
            fields_with_source=fields_with_source,
        )

    except Exception as e:
        import traceback

        # traceback.print_exc()
        return render_template(
            "emissions-scope/partials/form-detail-modal.html",
            error=f"เกิดข้อผิดพลาด: {str(e)}",
        )


@module.route("/get-linked-field-info/<material_name>", methods=["GET"])
@login_required
def get_linked_field_info(material_name):
    """
    ดึงข้อมูลการลิงก์ของฟิลด์เฉพาะเจาะจง
    """
    try:
        field = request.args.get("field")
        month_id = request.args.get("month_id")
        year = request.args.get("year")

        # Query FormAndFormula, not Material
        form = FormAndFormula.objects(material_name=material_name).first()
        if not form:
            print(f"Form not found for material_name: {material_name}")
            return render_template(
                "emissions-scope/partials/linked-form-info-modal.html",
                error=f"ไม่พบฟอร์ม: {material_name}",
            )

        # หา input_type ที่ตรงกับ field
        input_type = None
        for inp in form.input_types:
            if inp.field == field:
                input_type = inp
                break

        if not input_type:
            print(f"Input type not found for field: {field}")
            print(f"Available fields: {[inp.field for inp in form.input_types]}")
            return render_template(
                "emissions-scope/partials/linked-form-info-modal.html",
                error=f"ไม่พบฟิลด์: {field}",
            )

        if not input_type.source_form_id:
            print(f"Field {field} is not a linked field (no source_form_id)")
            return render_template(
                "emissions-scope/partials/linked-form-info-modal.html",
                error="ฟิลด์นี้ไม่ได้ลิงก์มาจากฟอร์มอื่น",
            )

        # ดึงข้อมูลฟอร์มต้นฉบับ
        source_forms_data = []
        from bson import ObjectId
        
        try:
            source_form = FormAndFormula.objects(id=ObjectId(input_type.source_form_id)).first()
            if source_form:
                print(f"Found source form: {source_form.material_name}")
                print(f"Looking for original_field: {input_type.original_field}")
                
                # ดึงข้อมูล Material จากฟอร์มต้นฉบับ
                source_material = Material.objects(
                    name=source_form.material_name,
                    month=int(month_id),
                    year=int(year),
                    department=current_user.department_key,
                    campus=current_user.campus_id,
                ).first()

                # หาค่าของฟิลด์ต้นฉบับ
                source_value = None
                if source_material and input_type.original_field:
                    print(f"Source material found, quantity_type count: {len(source_material.quantity_type) if source_material.quantity_type else 0}")
                    for qt in source_material.quantity_type:
                        print(f"  - Checking field: {qt.field} == {input_type.original_field}?")
                        if qt.field == input_type.original_field:
                            source_value = qt.amount
                            print(f"  - Found value: {source_value}")
                            break

                source_forms_data.append({
                    "form": source_form,
                    "material": source_material,
                    "field_name": input_type.original_field or input_type.field,
                    "field_label": input_type.label,
                    "field_value": source_value,
                })
                print(f"Added source form data, field_value: {source_value}")
            else:
                print(f"Source form not found for id: {input_type.source_form_id}")
        except Exception as e:
            print(f"Error fetching source form: {str(e)}")
            import traceback
            traceback.print_exc()

        print(f"Returning {len(source_forms_data)} source forms")
        return render_template(
            "emissions-scope/partials/linked-form-info-modal.html",
            form=form,
            current_field=input_type,
            source_forms=source_forms_data,
            month_id=month_id,
            year=year,
        )

    except Exception as e:
        print(f"ERROR in get_linked_field_info: {str(e)}")
        import traceback
        traceback.print_exc()
        return render_template(
            "emissions-scope/partials/linked-form-info-modal.html",
            error=f"เกิดข้อผิดพลาด: {str(e)}",
        )


@module.route("/get-linked-form-info/<material_name>", methods=["GET"])
@login_required
def get_linked_form_info(material_name):
    """
    ดึงข้อมูลการลิงก์สำหรับแสดงในตารางเมื่อคลิกที่ข้อมูลลิงก์
    """
    try:
        month_id = request.args.get("month_id")
        year = request.args.get("year")

        form = FormAndFormula.objects(material_name=material_name).first()
        if not form:
            return render_template(
                "emissions-scope/partials/linked-form-info-modal.html",
                error="ไม่พบฟอร์มที่ต้องการ",
            )

        # ดึงข้อมูลฟอร์มต้นทาง
        source_forms_data = []

        if getattr(form, "is_linked", False) and getattr(form, "linked_forms", []):
            from bson import ObjectId
            for form_id in form.linked_forms:
                try:
                    source_form = FormAndFormula.objects(id=ObjectId(form_id)).first()
                    if source_form:
                        # ดึงข้อมูล Material ต้นทางในเดือนเดียวกัน
                        source_material_data = Material.objects(
                            month=int(month_id),
                            name=source_form.material_name,
                            scope=int(source_form.ghg_scope),
                            sub_scope=int(source_form.ghg_sup_scope),
                            year=int(year),
                            department=current_user.department_key,
                            campus=current_user.campus_id,
                        ).first()
                        
                        source_forms_data.append({
                            "form": source_form,
                            "material": source_material_data
                        })
                except:
                    continue

        return render_template(
            "emissions-scope/partials/linked-form-info-modal.html",
            form=form,
            source_forms=source_forms_data,
            month_id=month_id,
            year=year,
        )

    except Exception as e:
        import traceback

        # traceback.print_exc()
        return render_template(
            "emissions-scope/partials/linked-form-info-modal.html",
            error=f"เกิดข้อผิดพลาด: {str(e)}",
        )
