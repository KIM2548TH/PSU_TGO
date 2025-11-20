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
        # print(f"Error getting user scopes: {e}")
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
        # print(f"Error getting current scope index: {e}")
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
    all_input_types = []
    for head in head_table:
        form_and_formula_item = FormAndFormula.objects(material_name=head).first()
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
@permissions_required_all(["เข้าถึงหน้าข้อมูลการปล่อย"])
def view_emissions():
    # รับค่า scope_id และ sub_scope_id จาก POST request
    scope_id = request.form.get("scope_id")
    sub_scope_id = request.form.get("sub_scope_id")
    selected_year = request.form.get("year_form_scope")
    quick_edit = request.form.get("quick_edit", "false").lower() == "true"

    # print(f"view_emissions received quick_edit: {quick_edit}")

    # ดึงปีจาก Material
    years = sorted(Material.objects().distinct("year"))
    # ถ้ามีปีใน database ใช้ปีแรก, ถ้าไม่มีให้ใช้ปีปัจจุบัน
    start_year = years[0] if years else datetime.datetime.now().year
    # ปีปัจจุบัน
    current_year = datetime.datetime.now().year
    years = list(range(start_year, current_year + 1))
    # year_list = list(range(start_year, current_year + 1))
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

    # print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>", selected_year)
    return render_template(
        "emissions-scope/view-emissions.html",
        scope_id=scope_id,
        sub_scope_id=sub_scope_id,
        user=current_user,
        years=years,
        ghg_name=ghg_name,
        current_year=current_year,  # ส่งปีปัจจุบันไปยังเทมเพลต
        selected_year=int(selected_year),  # ใช้ปีที่เลือกหรือปีปัจจุบัน
        user_scopes=user_scopes,
        current_scope_index=current_scope_index,
        quick_edit=quick_edit,  # ส่ง quick_edit state ไปยัง template
    )


@module.route("/load-emissions-table", methods=["GET", "POST"])
@login_required
def load_emissions_table():
    scope_id = request.args.get("scope_id")
    sub_scope_id = request.args.get("sub_scope_id")

    # Handle URL encoding issue - check for malformed parameter names
    if not sub_scope_id and request.args.get("amp;sub_scope_id"):
        sub_scope_id = request.args.get("amp;sub_scope_id")
        # print("Found malformed sub_scope_id parameter, corrected it")

    year = request.args.get("year") or datetime.datetime.now().year
    page = int(request.args.get("page", 1))

    # Validate required parameters
    if not scope_id or not sub_scope_id:
        # print(
        # f"Missing required parameters: scope_id={scope_id}, sub_scope_id={sub_scope_id}"
        # )
        return jsonify({"error": "Missing required parameters"}), 400

    # Check for quick_edit parameter from both args and form data
    quick_edit_param = request.args.get("quick_edit") or request.form.get("quick_edit")
    quick_edit = False

    # Multiple ways to check for quick_edit
    if quick_edit_param:
        if isinstance(quick_edit_param, str):
            quick_edit = quick_edit_param.lower() == "true"
        elif quick_edit_param is True:
            quick_edit = True

    # Debug information
    # print(f"=== LOAD EMISSIONS TABLE DEBUG ===")
    # print(f"Request method: {request.method}")
    # print(f"Request URL: {request.url}")
    # print(f"Request args: {dict(request.args)}")
    # print(f"Request form: {dict(request.form)}")
    # print(f"HX-Request header: {request.headers.get('HX-Request')}")
    # print(f"Quick edit param raw: {repr(quick_edit_param)}")
    # print(f"Quick edit mode final: {quick_edit}")
    # print(f"==================================")

    scope = Scope.objects(
        ghg_scope=int(scope_id),
        ghg_sup_scope=int(sub_scope_id),
        campus=current_user.campus_id,
        department=current_user.department_key,
    ).first()
    if not scope:
        return jsonify({"error": "Scope not found"}), 404

    head_table = scope.head_table

    # Use new function to calculate grouped input types
    current_headers, materials_form, total_pages, items_per_page = (
        calculate_grouped_input_types(head_table, page)
    )

    # ดึงข้อมูลฟอร์มสำหรับแต่ละ header
    head_table_info = {}
    for head in current_headers:
        form = FormAndFormula.objects(material_name=head).first()
        if form:
            head_table_info[head] = {
                "is_linked": getattr(form, "is_linked", False),
                "linked_material_name": getattr(form, "linked_material_name", ""),
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

    # Always handle HTMX requests and initial page loads
    # For debugging: Always render the template to see what's happening
    # Choose template based on edit mode
    template_name = (
        "emissions-scope/partials/quick-edit-table.html"
        if quick_edit
        else "emissions-scope/partials/emissions-table.html"
    )

    # print(f"Using template: {template_name} (Quick Edit: {quick_edit})")

    # Force quick edit template for testing
    if request.args.get("force_quick") == "true":
        template_name = "emissions-scope/partials/quick-edit-table.html"
        # print("FORCED Quick Edit template!")

    return render_template(
        template_name,
        scope=scope,
        scope_id=scope_id,
        sub_scope_id=sub_scope_id,
        materials=materials,
        head_table=current_headers,
        head_table_info=head_table_info,  # เพิ่มข้อมูลฟอร์ม
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

    # ตรวจสอบข้อมูลที่จำเป็น
    if not month_id or not head:
        return jsonify({"error": "Invalid month or head"}), 400

    # ✅ ลบการสร้าง MaterialForm ที่ไม่จำเป็น - ใช้ validation ใน backend แล้ว
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
        unit=unit,  # ส่งค่า unit ไปยังเทมเพลต
    )


@module.route("/load-materials-form", methods=["GET"])
@login_required
def load_materials_form():
    month_id = request.args.get("month_id")
    year = request.args.get("year")
    scope_id = request.args.get("scope_id")
    sub_scope_id = request.args.get("sub_scope_id")
    month = request.args.get("month")
    # print("<<<<<<<<<<<<<<<<<<<<<<", scope_id, sub_scope_id, month_id, year)

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


# สมมติว่าคลาสเหล่านี้มีการกำหนดไว้แล้ว (จากโค้ดเดิมของคุณ)
# class FormAndFormula:
#     ...
#
# class Material:
#     ...


def calculate_result(material):
    """
    คำนวณผลลัพธ์จากสูตรและบันทึก result และ result2 ลงใน material
    พร้อมทั้งคำนวณผลลัพธ์ก๊าซทั้ง 7 ชนิด
    """
    # ดึงข้อมูลสูตรจากฐานข้อมูล
    form_and_formula = FormAndFormula.objects(material_name=material.name).first()
    if not form_and_formula:
        print(f"ไม่พบสูตรสำหรับ material: {material.name}")
        return

    # สร้าง mapping ระหว่างชื่อตัวแปรภาษาไทย กับชื่อที่ปลอดภัย
    variable_mapping = {
        original_var: f"var_{i}"
        for i, original_var in enumerate(form_and_formula.variables)
    }

    sanitized_variables = {}
    for safe_name in variable_mapping.values():
        sanitized_variables[safe_name] = 0

    for qt in material.quantity_type:
        if qt.field in variable_mapping:
            safe_name = variable_mapping[qt.field]
            sanitized_variables[safe_name] = qt.amount

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
                # print(f"เกิดข้อผิดพลาดในการคำนวณ result2 สำหรับ : {e}")
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
            # print(f"เกิดข้อผิดพลาดในการคำนวณผลลัพธ์ก๊าซ: {e}")
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
        print(f"เกิดข้อผิดพลาดในการคำนวณผลลัพธ์สำหรับ {material.name}: {e}")
        print("--- Debug Information ---")
        print(f"Original formula: {form_and_formula.formula}")
        print(f"Sanitized formula: {sanitized_formula}")
        print(f"Sanitized variables: {sanitized_variables}")
        # print("-----------------------")


def save_material(scope_id, sub_scope_id, month_id, year, material_data):
    """
    Save a single material to the database และคำนวณ result
    """
    head = material_data["head"]
    field = material_data["field"]
    amount = material_data["amount"]

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
    calculate_result(material)

    # จัดการ Material ที่ลิงก์
    linked_formulas = FormAndFormula.objects(linked_material_name=head, is_linked=True)
    for linked_formula in linked_formulas:
        linked_material = Material.objects(
            month=int(month_id),
            name=linked_formula.material_name,
            scope=int(linked_formula.ghg_scope),
            sub_scope=int(linked_formula.ghg_sup_scope),
            year=year,
            department=current_user.department_key,
            campus=current_user.campus_id,
        ).first()

        # สร้าง quantity_type สำหรับ linked material โดยใช้ result จาก material ต้นฉบับ
        linked_quantity_types = []
        if material.result is not None:
            # ใช้ result จาก material ต้นฉบับเป็น input สำหรับ linked material
            # ดึง input_type แรกจาก linked_formula เพื่อใช้เป็น template
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

        if linked_material:
            # อัปเดต quantity_type ใหม่
            linked_material.quantity_type = linked_quantity_types
            linked_material.is_linked = True
            linked_material.edit_by_id = str(current_user.id)
            linked_material.update_date = datetime.datetime.now()
            linked_material.save()

            # คำนวณ result ใหม่ตามสูตรของ linked material
            calculate_result(linked_material)
        else:
            # สร้าง material ใหม่
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
            calculate_result(linked_material)

    return True


@module.route("/save-materials", methods=["POST"])
@login_required
@permissions_required_all(["เซฟข้อมูลการปล่อย"])
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

        # ตรวจสอบว่า material นี้ไม่ถูกลิงก์
        matched_material = Material.objects(
            name=material_data["head"],
            scope=int(scope_id),
            sub_scope=int(sub_scope_id),
            year=int(year),
            department=current_user.department_key,
            campus=current_user.campus_id,
        ).first()
        if matched_material and matched_material.is_linked:
            continue  # ข้าม material ที่ถูกลิงก์

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

    # สร้าง head_table_info สำหรับ current_headers
    head_table_info = {}
    for head in current_headers:
        form = FormAndFormula.objects(material_name=head).first()
        if form:
            head_table_info[head] = {
                "is_linked": getattr(form, "is_linked", False),
                "linked_material_name": getattr(form, "linked_material_name", ""),
                "desc_form": form.desc_form,
                "formula": form.formula,
            }

    # สร้าง materials_form ใหม่ตาม current_headers
    materials_form = []
    for head in current_headers:
        form_and_formula = FormAndFormula.objects(material_name=head).first()
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

        # จัดการ Material ที่ลิงก์ - ต้องอัปเดตข้อมูลใหม่
        linked_formulas = FormAndFormula.objects(
            linked_material_name=head, is_linked=True
        )
        for linked_formula in linked_formulas:
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

    return True


@module.route("/delete-material", methods=["POST"])
@login_required
@permissions_required_all(["ลบข้อมูลการปล่อย"])
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
                "linked_material_name": getattr(form, "linked_material_name", ""),
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
@permissions_required_all(["ลบข้อมูลการปล่อยกทั้งหมด"])
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

            # อัปเดต linked materials สำหรับทุก material ที่ถูกลบ
            for material_name in materials_to_update_linked:
                linked_formulas = FormAndFormula.objects(
                    linked_material_name=material_name, is_linked=True
                )
                for linked_formula in linked_formulas:
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
                    "linked_material_name": getattr(form, "linked_material_name", ""),
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
@permissions_required_all(["อัปโหลดไฟล์ข้อมูลการปล่อย"])
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
@permissions_required_all(["โหลดข้อมูลการปล่อย"])
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
@permissions_required_all(["ลบไฟล์ข้อมูลการปล่อย"])
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
        source_form = None
        if getattr(form, "is_linked", False) and getattr(
            form, "linked_material_name", ""
        ):
            source_form = FormAndFormula.objects(
                material_name=form.linked_material_name
            ).first()

            if source_form:
                source_scope = Scope.objects(
                    ghg_scope=source_form.ghg_scope,
                    ghg_sup_scope=source_form.ghg_sup_scope,
                ).first()
                source_form.scope_name = (
                    source_scope.ghg_name if source_scope else "Unknown"
                )

        # ดึงรายชื่อฟอร์มที่ลิงก์มาจากฟอร์มนี้
        linked_forms = []
        if not getattr(form, "is_linked", False):
            linked_forms_query = FormAndFormula.objects(
                linked_material_name=material_name, is_linked=True
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

        return render_template(
            "emissions-scope/partials/form-detail-modal.html",
            form=form,
            scope_info=scope_info,
            source_form=source_form,
            linked_forms=linked_forms,
        )

    except Exception as e:
        import traceback

        # traceback.print_exc()
        return render_template(
            "emissions-scope/partials/form-detail-modal.html",
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
        source_form = None
        source_material_data = None

        if getattr(form, "is_linked", False) and getattr(
            form, "linked_material_name", ""
        ):
            source_form = FormAndFormula.objects(
                material_name=form.linked_material_name
            ).first()

            if source_form:
                # ดึงข้อมูล Material ต้นทางในเดือนเดียวกัน
                source_material_data = Material.objects(
                    month=int(month_id),
                    name=form.linked_material_name,
                    year=int(year),
                    department=current_user.department_key,
                    campus=current_user.campus_id,
                ).first()

        return render_template(
            "emissions-scope/partials/linked-form-info-modal.html",
            form=form,
            source_form=source_form,
            source_material_data=source_material_data,
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
