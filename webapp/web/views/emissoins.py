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
from ..forms.material_form import MaterialForm
import datetime
import re
from ...models.file_model import ReferenceDocument, UploadedFile
from urllib.parse import quote

module = Blueprint("emissions", __name__, url_prefix="/emissions")


def calculate_grouped_input_types(head_table, page):
    """
    Calculate and group input types by headers for pagination.

    Args:
        head_table (list): List of headers from the scope.
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

    # Determine which subcategories to display on the current page
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
def view_emissions():
    # รับค่า scope_id และ sub_scope_id จาก POST request
    scope_id = request.form.get("scope_id")
    sub_scope_id = request.form.get("sub_scope_id")
    selected_year = request.form.get("year_form_scope")
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
    print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>", selected_year)
    return render_template(
        "emissions-scope/view-emissions.html",
        scope_id=scope_id,
        sub_scope_id=sub_scope_id,
        user=current_user,
        years=years,
        ghg_name=ghg_name,
        current_year=current_year,  # ส่งปีปัจจุบันไปยังเทมเพลต
        selected_year=int(selected_year),  # ใช้ปีที่เลือกหรือปีปัจจุบัน
    )


@module.route("/load-emissions-table", methods=["GET"])
@login_required
def load_emissions_table():
    scope_id = request.args.get("scope_id")
    sub_scope_id = request.args.get("sub_scope_id")
    year = request.args.get("year") or datetime.datetime.now().year
    page = int(request.args.get("page", 1))

    scope = Scope.objects(
        ghg_scope=int(scope_id),
        ghg_sup_scope=int(sub_scope_id),
        campus=current_user.campus_id,
        department=current_user.department_key,
    ).first()
    if not scope:
        return jsonify({"error": "Scope not found"}), 404

    head_table = scope.head_table

    # Use the new function to calculate grouped input types
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

    if request.headers.get("HX-Request"):
        return render_template(
            "emissions-scope/partials/emissions-table.html",
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
        )

    return render_template(
        "emissions-scope/view-emissions.html",
        scope_id=scope_id,
        sub_scope_id=sub_scope_id,
        user=current_user,
        year=year,
        materials_form=materials_form,
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
        print("Missing month_id or head in request")
        return jsonify({"error": "Invalid month or head"}), 400

    # สร้างฟอร์มใหม่
    form = MaterialForm()
    return render_template(
        "emissions-scope/partials/material-form.html",
        form=form,
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
    print("<<<<<<<<<<<<<<<<<<<<<<", scope_id, sub_scope_id, month_id, year)

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


# สมมติว่าคลาสเหล่านี้มีการ địnhหมาย ไว้แล้ว (จากโค้ดเดิมของคุณ)
# class FormAndFormula:
#     ...
#
# class Material:
#     ...


def calculate_result(material):
    """
    คำนวณผลลัพธ์จากสูตรและบันทึก result ลงใน material
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
        print(f"Executing sanitized formula: {sanitized_formula}")
        print(f"With variables: {sanitized_variables}")

        # คำนวณผลลัพธ์
        eval_result = eval(sanitized_formula, {}, sanitized_variables)

        # บันทึกผลลัพธ์ลงใน material.result
        material.result = eval_result
        material.update_date = datetime.datetime.now()
        material.save()

        print(f"คำนวณผลลัพธ์สำหรับ {material.name} สำเร็จ: {material.result}")

    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการคำนวณผลลัพธ์สำหรับ {material.name}: {e}")
        print("--- Debug Information ---")
        print(f"Original formula: {form_and_formula.formula}")
        print(f"Sanitized formula: {sanitized_formula}")
        print(f"Sanitized variables: {sanitized_variables}")
        print("-----------------------")


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
        print(f"Form and Formula not found for material: {head}")
        return False

    # ค้นหา InputType ที่ตรงกับ field
    input_type = form_and_formula.input_types.filter(field=field).first()
    if not input_type:
        print(f"Input type not found for field: {field} in material: {head}")
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

        if linked_material:
            linked_material.quantity_type = material.quantity_type
            linked_material.result = material.result
            linked_material.is_linked = True  # ตั้งค่า is_linked เป็น True
            linked_material.edit_by_id = str(current_user.id)
            linked_material.update_date = datetime.datetime.now()
            linked_material.save()
        else:
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
                quantity_type=material.quantity_type,
                result=material.result,
                is_linked=True,  # ตั้งค่า is_linked เป็น True
            )
            linked_material.save()

    return True


@module.route("/save-materials", methods=["POST"])
@login_required
def save_materials():
    scope_id = request.form.get("scope_id")
    sub_scope_id = request.form.get("sub_scope_id")
    month_id = request.form.get("month_id")
    year = request.form.get("year")
    page = int(request.form.get("page", 1))  # รับค่าหน้าปัจจุบัน
    input_label = request.form.get("input_label")
    input_field = request.form.get("input_field")

    # Debugging: Print received form data
    print(f"Received form data: {request.form}")

    # ตรวจสอบว่า scope และ sub_scope มีอยู่ในฐานข้อมูล
    scope = Scope.objects(
        ghg_scope=int(scope_id),
        ghg_sup_scope=int(sub_scope_id),
        department=current_user.department_key,
        campus=current_user.campus_id,
    ).first()

    if not scope:
        print(
            f"Invalid scope or sub-scope ID: scope_id={scope_id}, sub_scope_id={sub_scope_id}"
        )
        return jsonify({"error": "Invalid scope or sub-scope ID"}), 400

    head_table = scope.head_table
    print(f"Head table before saving materials: {head_table}")  # Debugging

    # Extract materials from form
    materials = []
    if "head" in request.form and "amount" in request.form:
        # Single material case (from material-form.html)
        head = request.form.get("head")
        amount = request.form.get("amount")

        form_and_formula = FormAndFormula.objects(material_name=head).first()
        if not form_and_formula:
            print(f"Form and Formula not found for material: {head}")
            return jsonify({"error": "Form and Formula not found"}), 400

        # label = input_label
        field = input_field
        if not field:
            print(f"No input types found for material: {head}")
            return jsonify({"error": "No input types found"}), 400

        materials.append({"head": head, "field": field, "amount": amount})
    else:
        # Multiple materials case (from materials-form.html)
        for key in request.form.keys():
            if key.startswith("amount_"):
                parts = key.split("_")
                if len(parts) < 3:
                    print(f"Invalid key format: {key}")
                    continue
                head = parts[1]
                field = parts[2]
                amount = request.form.get(key)

                # เพิ่มเงื่อนไขตรวจสอบ amount ก่อน append
                if amount and amount.strip():  # เซฟเฉพาะฟิลด์ที่มีการกรอกข้อมูล
                    materials.append({"head": head, "field": field, "amount": amount})

    # Debugging: Print materials data
    print(f"Materials: {materials}")

    if not scope_id or not sub_scope_id or not month_id or not year or not materials:
        print("Missing required data")
        return jsonify({"error": "Missing data"}), 400

    # Save each material
    for material_data in materials:
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

        save_material(scope_id, sub_scope_id, month_id, year, material_data)

    # Update emissions table
    head_table = scope.head_table  # Re-fetch head_table after saving materials
    print(f"Head table after saving materials: {head_table}")  # Debugging

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

    # กรองข้อมูล Material ตามปีที่เลือก
    materials = Material.objects(
        scope=int(scope_id),
        sub_scope=int(sub_scope_id),
        year=int(year),
        department=current_user.department_key,
        campus=current_user.campus_id,
    )

    if request.headers.get("HX-Request"):
        print(
            f"Rendering emissions table with scope_id: {scope_id}, sub_scope_id: {sub_scope_id}, year: {year}, page: {page}"
        )
        return render_template(
            "emissions-scope/partials/emissions-table.html",
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
        )
    else:
        return redirect(
            url_for(
                "emissions.view_emissions",
                scope_id=scope_id,
                sub_scope_id=sub_scope_id,
                year=year,
            )
        )


@module.route("/delete-material", methods=["POST"])
@login_required
def delete_material():
    scope_id = request.form.get("scope_id")
    sub_scope_id = request.form.get("sub_scope_id")
    month_id = request.form.get("month_id")
    year = request.form.get("year")
    head = request.form.get("head")
    input_field = request.form.get("input_field")
    page = int(request.form.get("page", 1))

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
        material.quantity_type = [
            qt for qt in material.quantity_type if qt.field != input_field
        ]
        material.edit_by_id = str(current_user.id)  # อัปเดต edit_by_id
        material.update_date = datetime.datetime.now()  # อัปเดต update_date
        material.save()

        # Calculate and update the result
        calculate_result(material)

    # Refresh the table after deletion
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

    if request.headers.get("HX-Request"):
        return render_template(
            "emissions-scope/partials/emissions-table.html",
            scope=scope,
            scope_id=scope_id,
            sub_scope_id=sub_scope_id,
            materials=materials,
            head_table=current_headers,
            head_table_info=head_table_info,  # เพิ่มบรรทัดนี้
            total_pages=total_pages,
            page=page,
            user=current_user,
            year=year,
            materials_form=materials_form,
            items_per_page=items_per_page,
        )


@module.route("/delete-all-materials", methods=["POST"])
@login_required
def delete_all_materials():
    scope_id = request.form.get("scope_id")
    sub_scope_id = request.form.get("sub_scope_id")
    month_id = request.form.get("month_id")
    year = request.form.get("year")
    page = int(request.form.get("page", 1))

    materials = Material.objects(
        month=int(month_id),
        scope=int(scope_id),
        sub_scope=int(sub_scope_id),
        year=int(year),
        department=current_user.department_key,
        campus=current_user.campus_id,
    )

    if materials:
        # ลบเฉพาะ material ที่ไม่ถูกลิงก์
        for material in materials:
            if material.is_linked:
                continue  # ข้าม material ที่ถูกลิงก์
            material.quantity_type = []  # Clear quantity_type
            material.edit_by_id = str(current_user.id)  # Update edit_by_id
            material.update_date = datetime.datetime.now()  # Update update_date
            material.save()

            # Calculate and update the result
            calculate_result(material)

    # Refresh the table after deletion
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

    if request.headers.get("HX-Request"):
        return render_template(
            "emissions-scope/partials/emissions-table.html",
            scope=scope,
            scope_id=scope_id,
            sub_scope_id=sub_scope_id,
            materials=materials,
            head_table=current_headers,
            head_table_info=head_table_info,  # เพิ่มบรรทัดนี้
            total_pages=total_pages,
            page=page,
            user=current_user,
            year=year,
            materials_form=materials_form,
            items_per_page=items_per_page,
        )


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
    print(
        f"month_id: {month_id}, year: {year}, scope_id: {scope_id}, sub_scope_id: {sub_scope_id}, month: {month}"
    )

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
def upload_file():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    scope_id = request.form.get("scope_id")
    sub_scope_id = request.form.get("sub_scope_id")
    year = request.form.get("year")
    month_id = request.form.get("month_id")
    month = request.form.get("month")  # เพิ่มการดึงค่า month

    # ตรวจสอบว่าค่าพารามิเตอร์ไม่เป็น None
    if not all([scope_id, sub_scope_id, year, month_id]):
        return jsonify({"error": "Missing required parameters"}), 400

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

    # ส่งค่าพารามิเตอร์ไปยัง load_upload_modal
    return load_upload_modal(
        month_id=month_id,
        year=year,
        scope_id=scope_id,
        sub_scope_id=sub_scope_id,
        month=month,
    )


@module.route("/download-file/<file_id>", methods=["GET"])
@login_required
def download_file(file_id):
    document = ReferenceDocument.objects(files__id=file_id).first()
    print(f"Downloading file with ID: {file_id}")
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
def delete_file(file_id):
    print(f"Deleting file with ID: {file_id}")
    scope_id = request.form.get("scope_id")
    sub_scope_id = request.form.get("sub_scope_id")
    year = request.form.get("year")
    month_id = request.form.get("month_id")
    month = request.form.get("month")  # เพิ่มการดึงค่า month

    if not file_id:
        print("Missing file_id")
        return jsonify({"error": "Missing file_id"}), 400

    document = ReferenceDocument.objects(files__id=file_id).first()
    if not document:
        print(f"Document not found for file_id: {file_id}")
        return jsonify({"error": "File not found"}), 404

    document.files = [f for f in document.files if str(f.id) != file_id]
    document.save()

    # ส่งค่าพารามิเตอร์ไปยัง load_upload_modal
    return load_upload_modal(
        month_id=month_id,
        year=year,
        scope_id=scope_id,
        sub_scope_id=sub_scope_id,
        month=month,
    )


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

        traceback.print_exc()
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

        traceback.print_exc()
        return render_template(
            "emissions-scope/partials/linked-form-info-modal.html",
            error=f"เกิดข้อผิดพลาด: {str(e)}",
        )
