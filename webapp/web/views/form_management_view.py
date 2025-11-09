from flask import Blueprint, render_template, redirect, url_for, request, jsonify, flash, make_response
from flask_login import login_required, logout_user, current_user
from ..forms.user_form import LoginForm, RegisterForm, EditUserForm, EditprofileForm
from ..forms.form_management_form import FormAndFormulaForm, InputFieldForm
from ...services.user_service import UserService
from ...models import User, Role, Permission, FormAndFormula, Scope, Material, InputType
from ..views.emissoins import calculate_result
from ..utils.acl import permissions_required_all
from ..utils.toast_utils import success_response, error_response, warning_response, info_response, ToastType
import datetime


module = Blueprint("form_management", __name__, url_prefix="/form-management")


@module.route("/", methods=["GET"])
@login_required
def form_management():
    """หน้าหลักจัดการฟอร์ม - ให้ทุกคนที่ login แล้วเข้าได้"""
    forms = FormAndFormula.objects().order_by(
        "ghg_scope", "ghg_sup_scope", "material_name"
    )

    # ดึงข้อมูล scope names จาก Scope model
    scopes = Scope.objects().order_by("ghg_scope", "ghg_sup_scope")
    scope_names = {}

    for scope in scopes:
        key = f"{scope.ghg_scope}.{scope.ghg_sup_scope}"
        scope_names[key] = scope.ghg_name

    return render_template(
        "/form-management/form-management.html", forms=forms, scope_names=scope_names
    )


# === FORM LOADING ROUTES ===
@module.route("/load-add-form", methods=["GET"])
@login_required
def load_add_form_and_formula():
    """โหลดหน้าเพิ่มฟอร์มใหม่ พร้อม default values"""
    # รับค่า default จาก query parameters
    default_scope = request.args.get("default_scope")
    default_sub_scope = request.args.get("default_sub_scope")
    
    return render_template(
        "/form-management/add-form-and-formula.html",
        default_scope=default_scope,
        default_sub_scope=default_sub_scope,
    )


@module.route("/load-edit-form", methods=["GET"])
@login_required
def load_edit_form_and_formula():
    """โหลดหน้าแก้ไขฟอร์ม"""
    form_id = request.args.get("form_id")

    if not form_id:
        return render_template(
            "/form-management/edit-form-and-formula.html",
            form=None,
            error_msg="No form ID provided",
        )

    try:
        from bson import ObjectId
        from bson.errors import InvalidId

        try:
            object_id = ObjectId(form_id)
        except InvalidId:
            return render_template(
                "/form-management/edit-form-and-formula.html",
                form=None,
                error_msg="Invalid form ID format",
            )

        # ดึงข้อมูลฟอร์มที่ต้องการแก้ไข
        form_obj = FormAndFormula.objects(id=object_id).first()
        if not form_obj:
            return render_template(
                "/form-management/edit-form-and-formula.html",
                form=None,
                error_msg="Form not found",
            )

        # แปลง FormAndFormula object เป็น dict สำหรับ template
        form_data = _convert_form_to_dict(form_obj)
        
        # เพิ่ม headers เพื่อป้องกัน cache
        response = make_response(
            render_template(
                "/form-management/edit-form-and-formula.html", 
                form=form_data
            )
        )
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return response

    except Exception as e:
        import traceback
        traceback.print_exc()
        return render_template(
            "/form-management/edit-form-and-formula.html",
            form=None,
            error_msg=f"Error loading form: {str(e)}",
        )


# === SCOPE MANAGEMENT ROUTES ===
@module.route("/scope/<int:scope_id>", methods=["GET"])
@login_required
def get_scope_content(scope_id):
    """โหลด content ตาม scope ที่เลือก"""
    try:
        # โหลดข้อมูลใหม่
        forms = FormAndFormula.objects().order_by(
            "ghg_scope", "ghg_sup_scope", "material_name"
        )
        
        scopes = Scope.objects().order_by("ghg_scope", "ghg_sup_scope")
        scope_names = {}
        for scope in scopes:
            key = f"{scope.ghg_scope}.{scope.ghg_sup_scope}"
            scope_names[key] = scope.ghg_name
        
        # รับพารามิเตอร์การกรอง
        filter_sub_scope = request.args.get('filter_sub_scope')
        show_all = request.args.get('show_all', 'false').lower() == 'true'
        
        # เลือก template ตาม scope
        template_map = {
            1: "form-management/partials/scope1-content.html",
            2: "form-management/partials/scope2-content.html",  
            3: "form-management/partials/scope3-content.html"
        }
        
        template_name = template_map.get(scope_id, template_map[1])
        
        return render_template(
            template_name,
            forms=forms,
            scope_names=scope_names,
            active_scope=str(scope_id),
            filter_sub_scope=int(filter_sub_scope) if filter_sub_scope else None,
            show_all=show_all
        )
    except Exception as e:
        return f'<div class="text-error">Error loading scope content: {str(e)}</div>'


# === CALCULATOR ROUTES ===
@module.route("/calculator/load-variables", methods=["POST"])
@login_required
def calculator_load_variables():
    """โหลด variable buttons สำหรับ calculator - แทน updateFormulaButtons()"""
    try:
        form_data = request.form.to_dict()
        variables = _get_calculator_variables(form_data)
        
        return render_template(
            "form-management/partials/calculator-variables.html",
            variables=variables
        )
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/calculator/show", methods=["POST"])
@login_required
def calculator_show():
    """แสดง/ซ่อน calculator dropdown แบบ toggle"""
    try:
        form_data = request.form.to_dict()
        variables = _get_calculator_variables(form_data)
        
        # สร้าง calculator HTML พร้อมปุ่มปิดที่ทำงานแบบ toggle
        calculator_html = render_template(
            "form-management/partials/calculator-dropdown.html",
            variables=variables
        )
        
        # แทนที่ปุ่ม X ให้ส่ง empty content กลับมา
        calculator_html = calculator_html.replace(
            'hx-post="/form-management/calculator/hide"',
            'hx-post="/form-management/calculator/hide"'
        )
        
        return calculator_html
        
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/calculator/hide", methods=["POST"])
@login_required
def calculator_hide():
    """ปิด calculator - ส่งคืน empty content"""
    return ""


@module.route("/calculator/check-existing", methods=["POST"])
@login_required
def calculator_check_existing():
    """เช็คว่า calculator มีอยู่หรือไม่"""
    return ""


@module.route("/calculator/add-value", methods=["POST"])
@login_required
def calculator_add_value():
    """เพิ่มค่าลงในสูตร"""
    try:
        current_formula = request.form.get('formula', '')
        new_value = request.form.get('value', '')
        updated_formula = current_formula + str(new_value)
        
        return render_template(
            "form-management/partials/formula-input.html",
            formula_value=updated_formula
        )
        
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/calculator/remove-last", methods=["POST"])
@login_required
def calculator_remove_last():
    """ลบตัวอักษรสุดท้ายในสูตร"""
    try:
        current_formula = request.form.get('formula', '')
        updated_formula = current_formula[:-1] if current_formula else ''
        
        return render_template(
            "form-management/partials/formula-input.html",
            formula_value=updated_formula
        )
        
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/calculator/clear", methods=["POST"])
@login_required
def calculator_clear():
    """ล้างสูตรทั้งหมด"""
    try:
        return render_template(
            "form-management/partials/formula-input.html",
            formula_value=""
        )
        
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


# === FORM BUILDER ROUTES ===
@module.route("/form-builder/add-input-field", methods=["POST"])
@login_required
def add_input_field_htmx():
    """เพิ่ม input field ใหม่ - แทน addInputField()"""
    try:
        field_index = request.form.get('field_index', 0)
        field_number = int(field_index) + 1
        
        return render_template(
            "form-management/partials/input-field-row.html",
            field_index=field_index,
            field_number=field_number
        )
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/form-builder/remove-input-field", methods=["DELETE"])
@login_required
def remove_input_field():
    """ลบ input field - แทน removeField()"""
    # Return empty response เพื่อลบ element (HTMX จะทำการลบ DOM element)
    return "", 200


@module.route("/form-builder/toggle-form-type", methods=["POST"])
@login_required
def toggle_form_type():
    """สลับระหว่าง normal และ linked form"""
    try:
        form_type = request.form.get('form_type', 'normal')
        
        if form_type == 'linked':
            # โหลด available materials
            available_materials = FormAndFormula.objects(is_linked=False).only('material_name', 'ghg_scope', 'ghg_sup_scope')
            return render_template(
                "form-management/partials/linked-form-section.html",
                materials=available_materials
            )
        else:
            return render_template(
                "form-management/partials/normal-form-section.html"
            )
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/form-builder/preview", methods=["POST"])
@login_required
def preview_form():
    """สร้าง form preview - แทน updatePreview()"""
    try:
        form_data = request.form.to_dict()
        
        # สร้าง preview HTML
        preview_data = {
            'material_name': form_data.get('material_name', ''),
            'desc_form': form_data.get('desc_form', ''),
            'formula': form_data.get('formula', ''),
            'desc_formula': form_data.get('desc_formula', ''),
            'formula2': form_data.get('formula2', ''),
            'desc_formula2': form_data.get('desc_formula2', ''),
            'is_linked': form_data.get('form_type') == 'linked',
            'linked_material_name': form_data.get('linked_material_name', ''),
            'input_fields': []
        }
        
        # ตรวจสอบว่าเป็น linked form หรือไม่
        if preview_data['is_linked'] and preview_data['linked_material_name']:
            # ดึงข้อมูลจาก linked material
            linked_material = FormAndFormula.objects(material_name=preview_data['linked_material_name']).first()
            if linked_material and linked_material.input_types:
                for input_type in linked_material.input_types:
                    preview_data['input_fields'].append({
                        'field': input_type.field,
                        'label': input_type.label,
                        'input_type': input_type.input_type,
                        'unit': input_type.unit or ''
                    })
        else:
            # รวบรวม input fields จาก form ปกติ
            fields = request.form.getlist('field')
            labels = request.form.getlist('label')
            input_types = request.form.getlist('input_type')
            units = request.form.getlist('unit')
            
            for i in range(len(fields)):
                if fields[i]:
                    preview_data['input_fields'].append({
                        'field': fields[i],
                        'label': labels[i] if i < len(labels) else '',
                        'input_type': input_types[i] if i < len(input_types) else 'text',
                        'unit': units[i] if i < len(units) else ''
                    })
        
        # เพิ่ม current datetime
        current_datetime = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
        
        return render_template(
            "form-management/partials/form-preview-panel.html",
            preview_data=preview_data,
            current_datetime=current_datetime
        )
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/form-builder/load-linked-fields", methods=["GET"])  
@login_required
def load_linked_fields():
    """โหลดฟิลด์ของ linked material"""
    material_name = request.args.get('material_name')
    
    if not material_name:
        return '<div class="text-center text-gray-500">กรุณาเลือก Material</div>'
    
    linked_material = FormAndFormula.objects(material_name=material_name).first()
    if not linked_material:
        return '<div class="text-center text-error">ไม่พบ Material ที่เลือก</div>'
    
    return render_template(
        "form-management/partials/linked-fields-preview.html",
        linked_material=linked_material
    )


# === MAIN CRUD OPERATIONS ===
@module.route("/add-form", methods=["POST"])
@login_required
@permissions_required_all(["เพิ่มฟอร์ม"])
def add_form_and_formula():
    """เพิ่มฟอร์มใหม่"""
    try:
        desc_form = request.form.get("desc_form")
        desc_formula = request.form.get("desc_formula")
        desc_formula2 = request.form.get("desc_formula2", "")
        material_name = request.form.get("material_name")
        formula = request.form.get("formula")
        formula2 = ""
        ghg_scope = request.form.get("scope")
        ghg_sup_scope = request.form.get("sup_scope")

        # เพิ่มการจัดการลิงก์
        form_type = request.form.get("form_type", "normal")
        is_linked = form_type == "linked"
        linked_material_name = request.form.get("linked_material_name", "")

        # ตรวจสอบข้อมูลที่จำเป็น
        if not material_name or not formula or not ghg_scope or not ghg_sup_scope:
            return _error_response("กรุณากรอกข้อมูลให้ครบถ้วน")

        # ตรวจสอบชื่อวัสดุซ้ำ
        existing_material = FormAndFormula.objects(material_name=material_name).first()
        if existing_material:
            return _error_response(f'ชื่อวัสดุ "{material_name}" มีอยู่แล้ว กรุณาใช้ชื่ออื่น')

        try:
            ghg_sup_scope_int = int(ghg_sup_scope)
        except ValueError:
            return _error_response("Sub Scope ต้องเป็นตัวเลขเท่านั้น")

        # สร้าง FormAndFormula object ใหม่
        new_form = FormAndFormula(
            desc_form=desc_form,
            desc_formula=desc_formula,
            desc_formula2=desc_formula2,
            material_name=material_name,
            formula=formula,
            formula2=formula2,
            ghg_scope=int(ghg_scope),
            ghg_sup_scope=ghg_sup_scope_int,
            is_linked=is_linked,
            linked_material_name=linked_material_name if is_linked else "",
        )

        if is_linked and linked_material_name:
            _setup_linked_form_fields(new_form, linked_material_name)
        else:
            _setup_normal_form_fields(new_form)
        
        new_form.save()
        
        return _success_response("เพิ่มฟอร์มสำเร็จ!", ghg_scope)

    except Exception as e:
        return _error_response(f"เกิดข้อผิดพลาด: {str(e)}")


@module.route("/edit-form", methods=["POST"])
@login_required
@permissions_required_all(["แก้ไขฟอร์ม"])
def edit_form_and_formula():
    """แก้ไขฟอร์ม"""
    form_id = request.form.get("form_id")
    if not form_id:
        return _error_response("No form ID provided")
        
    try:
        from bson import ObjectId
        form = FormAndFormula.objects(id=ObjectId(form_id)).first()
        if not form:
            return _error_response("Form not found")

        # อัปเดตข้อมูลพื้นฐาน
        form.material_name = request.form.get("material_name")
        form.desc_form = request.form.get("desc_form")
        form.desc_formula = request.form.get("desc_formula")
        form.desc_formula2 = request.form.get("desc_formula2")
        form.formula = request.form.get("formula")
        form.formula2 = request.form.get("formula2")

        # อัปเดต input fields สำหรับฟอร์มปกติเท่านั้น
        is_linked = getattr(form, "is_linked", False)
        if is_linked:
            # สำหรับ linked form ใช้ข้อมูลเดิม
            linked_material_name = getattr(form, "linked_material_name", "")
            if linked_material_name:
                _setup_linked_form_fields(form, linked_material_name)
        else:
            # ฟอร์มปกติ - อัปเดต input fields
            _setup_normal_form_fields(form)

        form.save()
        return _success_response("บันทึกการแก้ไขสำเร็จ!", form.ghg_scope)

    except Exception as e:
        return _error_response(f"Failed to update form: {str(e)}")


@module.route("/delete-form/<form_id>", methods=["DELETE"])
@login_required
@permissions_required_all(["ลบฟอร์ม"])
def delete_form(form_id):
    """ลบฟอร์ม"""
    try:
        from bson import ObjectId
        form = FormAndFormula.objects(id=ObjectId(form_id)).first()
        if not form:
            return _error_response("Form not found")
        
        form_name = form.material_name
        scope = form.ghg_scope
        form.delete()
        
        return _success_response(f"ลบฟอร์ม '{form_name}' สำเร็จ!", scope)
        
    except Exception as e:
        return _error_response(f"Error deleting form: {str(e)}")


# === HELPER METHODS ===
def _get_calculator_variables(form_data):
    """ดึง variables สำหรับ calculator"""
    variables = []
    form_type = form_data.get('form_type', 'normal')
    
    if form_type == 'linked':
        linked_material_name = form_data.get('linked_material_name')
        if linked_material_name:
            linked_form = FormAndFormula.objects(material_name=linked_material_name).first()
            if linked_form and linked_form.input_types:
                for input_type in linked_form.input_types:
                    variables.append({
                        'field': input_type.field,
                        'label': input_type.label,
                        'color': 'bg-pink-100 text-pink-800'
                    })
    else:
        # ดึงจาก input fields ปกติ
        fields = form_data.getlist('field') if hasattr(form_data, 'getlist') else request.form.getlist('field')
        labels = form_data.getlist('label') if hasattr(form_data, 'getlist') else request.form.getlist('label')
        for i, field in enumerate(fields):
            if field:
                label = labels[i] if i < len(labels) else field
                variables.append({
                    'field': field,
                    'label': label,
                    'color': 'bg-blue-100 text-blue-800'
                })
    
    return variables


def _setup_linked_form_fields(form_obj, linked_material_name):
    """ตั้งค่า input fields สำหรับ linked form"""
    linked_material = FormAndFormula.objects(material_name=linked_material_name).first()
    if linked_material and linked_material.input_types:
        input_fields = []
        variables = []
        for quantity in linked_material.input_types:
            input_fields.append(
                InputType.create_input(
                    field=quantity.field,
                    label=quantity.label,
                    input_type=quantity.input_type,
                    unit=quantity.unit,
                )
            )
            variables.append(quantity.field)
        form_obj.input_types = input_fields
        form_obj.variables = variables


def _setup_normal_form_fields(form_obj):
    """ตั้งค่า input fields สำหรับ normal form"""
    input_fields = []
    variables = []
    fields = request.form.getlist("field")
    labels = request.form.getlist("label")
    input_types = request.form.getlist("input_type")
    units = request.form.getlist("unit")

    for i in range(len(fields)):
        field = fields[i]
        label = labels[i] if i < len(labels) else ""
        input_type = input_types[i] if i < len(input_types) else "text"
        unit = units[i] if i < len(units) else ""

        if field and input_type:
            input_fields.append(
                InputType.create_input(field, label, input_type, unit)
            )
            variables.append(field)

    form_obj.input_types = input_fields
    form_obj.variables = variables


def _success_response(message, refresh_scope=None):
    """สร้าง success response พร้อม toast notification"""
    response = make_response('')
    import json
    import urllib.parse
    
    encoded_message = urllib.parse.quote(message)
    
    trigger_data = {
        "closeModal": True,
        "showSuccess": encoded_message
    }
    response.headers['HX-Trigger'] = json.dumps(trigger_data)
    
    if refresh_scope:
        response.headers['HX-Trigger-After-Swap'] = f'refreshScope{refresh_scope}'
    
    return response


def _error_response(message):
    """สร้าง error response"""
    response = make_response(f'<div class="alert alert-error"><span>{message}</span></div>')
    response.headers['HX-Retarget'] = '#modal-content'
    return response, 400


# === SUB SCOPE ROUTES ===
@module.route("/get-sub-scopes/<int:main_scope>", methods=["GET"])
@login_required
def get_sub_scopes(main_scope):
    """ดึง sub scopes ตาม main scope ที่เลือก และ render template"""
    try:
        print(f"get_sub_scopes called with main_scope: {main_scope}")
        print(f"Request args: {request.args}")

        # Query sub scopes จาก Scope model โดยใช้ ghg_scope และเรียงตาม ghg_sup_scope
        sub_scopes_query = Scope.objects(ghg_scope=main_scope).order_by("ghg_sup_scope")
        print(f"Found {len(sub_scopes_query)} sub scopes for scope {main_scope}")

        # ใช้ set เพื่อเก็บ ghg_sup_scope ที่ไม่ซ้ำ
        seen_sup_scopes = set()
        unique_sub_scopes = []

        for scope in sub_scopes_query:
            if scope.ghg_sup_scope not in seen_sup_scopes:
                seen_sup_scopes.add(scope.ghg_sup_scope)
                unique_sub_scopes.append(scope)
                print(f"Added sub scope: {scope.ghg_sup_scope} - {scope.ghg_name}")

        print(f"Unique sub scopes: {len(unique_sub_scopes)}")

        # รับค่า selected_value จาก query parameter (สำหรับ edit form)
        selected_value = request.args.get("selected", None)
        print(f"Selected value from query: {selected_value}")

        if selected_value:
            try:
                selected_value = int(selected_value)
                print(f"Converted selected value: {selected_value}")
            except ValueError:
                selected_value = None
                print("Failed to convert selected value to int")

        # Render template
        return render_template(
            "form-management/partials/sub-scope-select.html",
            sub_scopes=unique_sub_scopes,
            selected_value=selected_value,
        )

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in get_sub_scopes: {str(e)}")
        print(f"Full traceback: {error_details}")

        # Return simple error HTML
        return f'''
        <select name="sup_scope" class="select select-bordered w-full mt-1" required>
            <option value="">Error loading sub scopes: {str(e)}</option>
        </select>
        '''


@module.route("/form-builder/load-edit-fields", methods=["GET"])
@login_required
def load_edit_fields():
    """โหลด input fields สำหรับ edit form"""
    try:
        form_id = request.args.get('form_id')
        
        if not form_id:
            return render_template("form-management/partials/normal-form-section.html")
        
        from bson import ObjectId
        form_obj = FormAndFormula.objects(id=ObjectId(form_id)).first()
        
        if not form_obj or not form_obj.input_types:
            return render_template("form-management/partials/normal-form-section.html")
        
        # สร้าง HTML สำหรับ input fields ที่มีอยู่
        fields_html = []
        for i, input_type in enumerate(form_obj.input_types):
            field_html = f'''
            <div class="border border-gray-300 rounded-xl p-4 bg-gray-50 shadow-sm" data-index="input-{i}">
                <div class="flex justify-between items-center mb-3">
                    <h4 class="text-md font-semibold text-gray-600">Field #{i + 1}</h4>
                    <button type="button" class="btn btn-sm btn-error"
                            hx-delete="/form-management/form-builder/remove-input-field"
                            hx-target="closest [data-index]"
                            hx-swap="delete"
                            hx-confirm="ต้องการลบฟิลด์นี้หรือไม่?">✕</button>
                </div>
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <input name="field" class="input input-bordered w-full" 
                           placeholder="Field" value="{input_type.field}" required
                           hx-post="/form-management/form-builder/preview"
                           hx-target="#preview-content"
                           hx-trigger="change delay:500ms, keyup delay:800ms"
                           hx-include="closest form">
                    <input name="label" class="input input-bordered w-full" 
                           placeholder="Label" value="{input_type.label}"
                           hx-post="/form-management/form-builder/preview"
                           hx-target="#preview-content"  
                           hx-trigger="change delay:500ms, keyup delay:800ms"
                           hx-include="closest form">
                    <select name="input_type" class="select select-bordered w-full"
                            hx-post="/form-management/form-builder/preview"
                            hx-target="#preview-content"
                            hx-trigger="change"
                            hx-include="closest form">
                        <option value="number" {"selected" if input_type.input_type == "number" else ""}>Number</option>
                        <option value="text" {"selected" if input_type.input_type == "text" else ""}>Text</option>
                        <option value="select" {"selected" if input_type.input_type == "select" else ""}>Select</option>
                    </select>
                    <input name="unit" class="input input-bordered w-full" 
                           placeholder="Unit" value="{input_type.unit or ''}"
                           hx-post="/form-management/form-builder/preview"
                           hx-target="#preview-content"
                           hx-trigger="change delay:500ms, keyup delay:800ms"
                           hx-include="closest form">
                </div>
            </div>
            '''
            fields_html.append(field_html)
        
        # สร้าง complete HTML
        complete_html = f'''
        <div class="space-y-4">
            <div class="flex justify-between items-center">
                <h3 class="text-lg font-semibold text-gray-800">Input Fields</h3>
            </div>
            
            <div id="input-fields-container" class="space-y-3">
                {"".join(fields_html)}
            </div>
            
            <!-- ปุ่มเพิ่มฟิลด์แยกเป็นการ์ด -->
            <div class="card border border-dashed border-gray-300 bg-gray-50 p-6 flex items-center justify-center">
                <button type="button" class="btn btn-primary btn-sm"
                        hx-post="/form-management/form-builder/add-input-field"
                        hx-target="#input-fields-container"
                        hx-swap="beforeend"
                        hx-vals='{{"field_index": "{len(form_obj.input_types)}"}}'>
                    <i data-feather="plus" class="w-4 h-4 mr-1"></i>
                    เพิ่มฟิลด์ใหม่
                </button>
            </div>
            
            <div class="text-sm text-gray-500 bg-blue-50 p-3 rounded-lg">
                <i data-feather="info" class="inline w-4 h-4 mr-1"></i>
                กรุณาเพิ่ม input fields เพื่อกำหนดข้อมูลที่ต้องการรับจากผู้ใช้
            </div>
        </div>
        '''
        
        return complete_html
    except Exception as e:
        return f'<div class="text-error">Error loading edit fields: {str(e)}</div>'


@module.route("/get-available-materials", methods=["GET"])
@login_required
def get_available_materials():
    """ดึงรายชื่อ material ที่สามารถลิงก์ได้ - สำหรับ linked form"""
    try:
        # ดึง material ที่ไม่ใช่ฟอร์มลิงก์ (ฟอร์มปกติเท่านั้น)
        available_form = FormAndFormula.objects(is_linked=False).order_by("ghg_scope", "ghg_sup_scope", "material_name")
        
        return render_template(
            "form-management/partials/material-select.html",
            available_form=available_form,
        )
    except Exception as e:
        return f'<select name="linked_material_name" class="select select-bordered w-full mt-1"><option value="">Error: {str(e)}</option></select>'


# === TOAST NOTIFICATION ROUTES ===
@module.route("/toast/show", methods=["POST"])
@login_required
def show_toast():
    """แสดง toast notification"""
    message = request.form.get('message', 'สำเร็จ!')
    toast_type = request.form.get('type', 'success')
    
    return render_template(
        "components/toast-notification.html",
        message=message,
        type=toast_type
    )


@module.route("/components/toast/hide", methods=["DELETE"])
@login_required
def hide_toast():
    """ซ่อน toast notification"""
    return "", 200


# === UTILITY ROUTES ===
@module.route("/get-form-data/<form_id>", methods=["GET"])
@login_required
def get_form_data(form_id):
    """ดึงข้อมูลฟอร์มในรูปแบบ JSON"""
    try:
        from bson import ObjectId
        from bson.errors import InvalidId

        try:
            object_id = ObjectId(form_id)
        except InvalidId:
            return jsonify({"success": False, "message": "Invalid form ID format"})
        
        form = FormAndFormula.objects(id=object_id).first()
        if not form:
            return jsonify({"success": False, "message": "Form not found"})

        form_data = _convert_form_to_dict(form)
        return jsonify({"success": True, "form": form_data})
        
    except Exception as e:
        return jsonify({"success": False, "message": f"Error loading form: {str(e)}"})


def _convert_form_to_dict(form_obj):
    """แปลง FormAndFormula object เป็น dict"""
    return {
        "id": str(form_obj.id),
        "material_name": form_obj.material_name,
        "desc_form": form_obj.desc_form,
        "desc_formula": form_obj.desc_formula,
        "formula": form_obj.formula,
        "formula2": form_obj.formula2 or "",
        "ghg_scope": form_obj.ghg_scope,
        "ghg_sup_scope": form_obj.ghg_sup_scope,
        "is_linked": getattr(form_obj, "is_linked", False),
        "linked_material_name": getattr(form_obj, "linked_material_name", ""),
        "input_types": [
            {
                "field": input_field.field,
                "label": input_field.label,
                "input_type": input_field.input_type,
                "unit": input_field.unit,
            }
            for input_field in form_obj.input_types or []
        ]
    }
