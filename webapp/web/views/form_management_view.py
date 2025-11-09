from flask import Blueprint, render_template, redirect, url_for, request, jsonify, flash, make_response
from flask_login import login_required, logout_user, current_user
from ..forms.user_form import LoginForm, RegisterForm, EditUserForm, EditprofileForm
from ..forms.form_management_form import FormAndFormulaForm, InputFieldForm
from ...services.user_service import UserService
from ...models import User, Role, Permission, FormAndFormula, Scope, Material, InputType
from ..views.emissoins import calculate_result
from ..utils.acl import permissions_required_all
import datetime


module = Blueprint("form_management", __name__, url_prefix="/form-management")


@module.route("/", methods=["GET"])
@login_required
@permissions_required_all(["เข้าถึงหน้าแหล่งปล่อยก๊าซเรือนกระจก"])
def form_management():
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


# Calculator Routes (ใหม่)
@module.route("/calculator/load-variables", methods=["POST"])
@login_required
def calculator_load_variables():
    """โหลด variable buttons สำหรับ calculator - แทน updateFormulaButtons()"""
    try:
        form_data = request.form.to_dict()
        variables = []
        
        # ตรวจสอบว่าเป็น linked form หรือไม่
        form_type = form_data.get('form_type', 'normal')
        
        if (form_type == 'linked'):
            linked_material_name = form_data.get('linked_material_name')
            if linked_material_name:
                linked_form = FormAndFormula.objects(material_name=linked_material_name).first()
                if linked_form:
                    for input_type in linked_form.input_types:
                        variables.append({
                            'field': input_type.field,
                            'label': input_type.label,
                            'color': 'bg-pink-100 text-pink-800'
                        })
        else:
            # ดึงจาก input fields ปกติ
            fields = request.form.getlist('field')
            labels = request.form.getlist('label')
            for i, field in enumerate(fields):
                if field:
                    label = labels[i] if i < len(labels) else field
                    variables.append({
                        'field': field,
                        'label': label,
                        'color': 'bg-blue-100 text-blue-800'
                    })
        
        return render_template(
            "form-management/partials/calculator-variables.html",
            variables=variables
        )
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/calculator/add-to-formula", methods=["POST"])
@login_required  
def calculator_add_to_formula():
    """เพิ่มค่าลงในสูตร - แทน addToFormula()"""
    try:
        value = request.form.get('value', '')
        target = request.form.get('target', 'formula')  # formula หรือ formula2
        
        return jsonify({
            'success': True,
            'value': str(value),
            'target': target
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# Pure HTMX Calculator Routes (ไม่ใช้ JavaScript)
@module.route("/calculator/show", methods=["POST"])
@login_required
def calculator_show():
    """แสดง calculator dropdown - สร้าง container และโหลด calculator"""
    try:
        form_data = request.form.to_dict()
        
        # โหลด variables สำหรับ calculator
        variables = []
        form_type = form_data.get('form_type', 'normal')
        
        if form_type == 'linked':
            linked_material_name = form_data.get('linked_material_name')
            if linked_material_name:
                linked_form = FormAndFormula.objects(material_name=linked_material_name).first()
                if linked_form:
                    for input_type in linked_form.input_types:
                        variables.append({
                            'field': input_type.field,
                            'label': input_type.label,
                            'color': 'bg-pink-100 text-pink-800'
                        })
        else:
            # ดึงจาก input fields ปกติ
            fields = request.form.getlist('field')
            labels = request.form.getlist('label')
            for i, field in enumerate(fields):
                if field:
                    label = labels[i] if i < len(labels) else field
                    variables.append({
                        'field': field,
                        'label': label,
                        'color': 'bg-blue-100 text-blue-800'
                    })
        
        # สร้าง HTML ที่รวม container ด้วย
        calculator_html = render_template(
            "form-management/partials/calculator-dropdown.html",
            variables=variables
        )
        
        # ส่งคืน container div พร้อม ID
        return f'<div id="calculator-dropdown-container" class="absolute top-full left-0 right-0 z-50 mt-2">{calculator_html}</div>'
        
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'

@module.route("/calculator/hide", methods=["POST"])
@login_required
def calculator_hide():
    """ลบ calculator dropdown ออกทั้งหมด - ส่ง empty string เพื่อลบ element"""
    return ""


@module.route("/calculator/load-new", methods=["POST"])
@login_required
def calculator_load_new():
    """โหลด calculator ใหม่เมื่อไม่มีใน storage"""
    try:
        form_data = request.form.to_dict()
        
        # โหลด variables สำหรับ calculator
        variables = []
        form_type = form_data.get('form_type', 'normal')
        
        if form_type == 'linked':
            linked_material_name = form_data.get('linked_material_name')
            if linked_material_name:
                linked_form = FormAndFormula.objects(material_name=linked_material_name).first()
                if linked_form:
                    for input_type in linked_form.input_types:
                        variables.append({
                            'field': input_type.field,
                            'label': input_type.label,
                            'color': 'bg-pink-100 text-pink-800'
                        })
        else:
            # ดึงจาก input fields ปกติ
            fields = request.form.getlist('field')
            labels = request.form.getlist('label')
            for i, field in enumerate(fields):
                if field:
                    label = labels[i] if i < len(labels) else field
                    variables.append({
                        'field': field,
                        'label': label,
                        'color': 'bg-blue-100 text-blue-800'
                    })
        
        return render_template(
            "form-management/partials/calculator-dropdown.html",
            variables=variables
        )
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'

@module.route("/calculator/add-value", methods=["POST"])
@login_required
def calculator_add_value():
    """เพิ่มค่าลงในสูตร - Pure Python"""
    try:
        current_formula = request.form.get('formula', '')
        new_value = request.form.get('value', '')
        
        # เพิ่มค่าใหม่ลงในสูตร
        updated_formula = current_formula + str(new_value)
        
        # Return updated input element
        return f'<input type="text" name="formula" id="formula" class="input input-bordered w-full" placeholder="e.g. diesel * 2.68" value="{updated_formula}" hx-post="/form-management/form-builder/preview" hx-target="#preview-content" hx-trigger="keyup delay:800ms, change" hx-include="closest form" required>'
        
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'

@module.route("/calculator/remove-last", methods=["POST"])
@login_required
def calculator_remove_last():
    """ลบตัวอักษรสุดท้ายในสูตร"""
    try:
        current_formula = request.form.get('formula', '')
        
        # ลบตัวอักษรสุดท้าย
        updated_formula = current_formula[:-1] if current_formula else ''
        
        # Return updated input element
        return f'<input type="text" name="formula" id="formula" class="input input-bordered w-full" placeholder="e.g. diesel * 2.68" value="{updated_formula}" hx-post="/form-management/form-builder/preview" hx-target="#preview-content" hx-trigger="keyup delay:800ms, change" hx-include="closest form" required>'
        
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'

@module.route("/calculator/clear", methods=["POST"])
@login_required
def calculator_clear():
    """ล้างสูตรทั้งหมด"""
    try:
        # Return cleared input element
        return '<input type="text" name="formula" id="formula" class="input input-bordered w-full" placeholder="e.g. diesel * 2.68" value="" hx-post="/form-management/form-builder/preview" hx-target="#preview-content" hx-trigger="keyup delay:800ms, change" hx-include="closest form" required>'
        
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


# Form Builder Routes (ใหม่)
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


@module.route("/form-builder/toggle-form-type", methods=["POST"])
@login_required
def toggle_form_type():
    """สลับระหว่าง normal และ linked form"""
    try:
        form_type = request.form.get('form_type', 'normal')
        
        if form_type == 'linked':
            # โหลด available materials
            available_materials = FormAndFormula.objects(is_linked=False).only('material_name')
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
        from datetime import datetime
        current_datetime = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        return render_template(
            "form-management/partials/form-preview-panel.html",
            preview_data=preview_data,
            current_datetime=current_datetime
        )
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/get-sub-scopes/<int:main_scope>", methods=["GET"])
@login_required
def get_sub_scopes(main_scope):
    """
    ดึง sub scopes ตาม main scope ที่เลือก และ render template
    """
    try:
        print(f"get_sub_scopes called with main_scope: {main_scope}")
        print(f"Request args: {request.args}")
        print(f"Request values: {request.values}")

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
        template_content = render_template(
            "form-management/partials/sub-scope-select.html",
            sub_scopes=unique_sub_scopes,
            selected_value=selected_value,
        )

        print(f"Template rendered successfully, length: {len(template_content)}")
        return template_content

    except Exception as e:
        import traceback

        error_details = traceback.format_exc()
        print(f"Error in get_sub_scopes: {str(e)}")
        print(f"Full traceback: {error_details}")

        # Return simple error HTML
        error_html = f"""
        <select name="sup_scope" id="sub-scope" class="select select-bordered w-full mt-1" required>
            <option value="">Error loading sub scopes: {str(e)}</option>
        </select>
        """
        return error_html


@module.route("/load-add-form", methods=["GET"])
@login_required
@permissions_required_all(["เพิ่มฟอร์ม"])
def load_add_form_and_formula():
    """โหลดหน้าเพิ่มฟอร์มใหม่ พร้อม WTF-Forms"""
    form = FormAndFormulaForm()
    
    # ตั้งค่า choices สำหรับ sub_scope dropdown
    default_scope = request.args.get("default_scope", None)
    default_sub_scope = request.args.get("default_sub_scope", None)
    
    if default_scope:
        form.scope.data = int(default_scope)
        
        # โหลด sub_scopes สำหรับ scope ที่เลือก
        sub_scopes_query = Scope.objects(ghg_scope=int(default_scope)).order_by("ghg_sup_scope")
        seen_sup_scopes = set()
        unique_sub_scopes = []
        
        for scope in sub_scopes_query:
            if scope.ghg_sup_scope not in seen_sup_scopes:
                seen_sup_scopes.add(scope.ghg_sup_scope)
                unique_sub_scopes.append((scope.ghg_sup_scope, f"{scope.ghg_sup_scope} - {scope.ghg_name}"))
        
        form.sup_scope.choices = unique_sub_scopes
        
        if default_sub_scope:
            form.sup_scope.data = int(default_sub_scope)

    return render_template(
        "/form-management/add-form-and-formula.html",
        form=form,
        default_scope=default_scope,
        default_sub_scope=default_sub_scope,
    )


@module.route("/form-builder/remove-input-field", methods=["DELETE"])
@login_required
def remove_input_field():
    """ลบ input field - แทน removeField()"""
    # Return empty response เพื่อลบ element (HTMX จะทำการลบ DOM element)
    return "", 200


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


# อัปเดต edit_form_and_formula function เพื่อรองรับ scope
@module.route("/edit-form", methods=["POST"])
@login_required
def edit_form_and_formula():
    form_id = request.form.get("form_id")
    if not form_id:
        from flask import make_response
        response = make_response('<div class="alert alert-error"><span>No form ID provided</span></div>')
        response.headers['HX-Retarget'] = '#modal-content'
        return response, 400
        
    try:
        from bson import ObjectId

        form = FormAndFormula.objects(id=ObjectId(form_id)).first()
        if not form:
            from flask import make_response
            response = make_response('<div class="alert alert-error"><span>Form not found</span></div>')
            response.headers['HX-Retarget'] = '#modal-content'
            return response, 404

        # อัปเดตข้อมูลพื้นฐาน
        form.material_name = request.form.get("material_name")
        form.desc_form = request.form.get("desc_form")
        form.desc_formula = request.form.get("desc_formula")
        form.desc_formula2 = request.form.get("desc_formula2")
        form.formula = request.form.get("formula")
        form.formula2 = request.form.get("formula2")

        ghg_scope = request.form.get("scope")
        ghg_sup_scope = request.form.get("sup_scope")
        if ghg_scope and ghg_sup_scope:
            form.ghg_scope = int(ghg_scope)
            try:
                form.ghg_sup_scope = int(ghg_sup_scope)
            except ValueError:
                from flask import make_response
                response = make_response('<div class="alert alert-error"><span>Sub Scope ต้องเป็นตัวเลขเท่านั้น</span></div>')
                response.headers['HX-Retarget'] = '#modal-content'
                return response, 400

        # ตรวจสอบว่าเป็นฟอร์มลิงก์หรือไม่ (ใช้ข้อมูลจาก database)
        is_linked = getattr(form, "is_linked", False)

        print(f"Debug - Current form is_linked: {is_linked}")
        print(f"Debug - Form linked_material_name: {getattr(form, 'linked_material_name', '')}")

        if is_linked:
            # ใช้ linked_material_name ที่มีอยู่แล้วใน database
            linked_material_name = getattr(form, "linked_material_name", "")
            
            if not linked_material_name:
                from flask import make_response
                response = make_response('<div class="alert alert-error"><span>ฟอร์มลิงก์นี้ไม่มีการระบุ Material ต้นทาง กรุณาติดต่อผู้ดูแลระบบ</span></div>')
                response.headers['HX-Retarget'] = '#modal-content'
                return response, 400
            
            # ดึงข้อมูล material ต้นฉบับ
            linked_material = FormAndFormula.objects(
                material_name=linked_material_name
            ).first()
            if not linked_material:
                from flask import make_response
                response = make_response(f'<div class="alert alert-error"><span>Material "{linked_material_name}" ไม่พบในระบบ กรุณาติดต่อผู้ดูแลระบบ</span></div>')
                response.headers['HX-Retarget'] = '#modal-content'
                return response, 404

            # ใช้ input_types ของ material ต้นฉบับ (ไม่เปลี่ยน)
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

            form.input_types = input_fields
            form.variables = variables
            
            print(f"Debug - Updated linked form variables: {variables}")
        else:
            # ฟอร์มปกติ - อัปเดต input fields จากฟอร์ม
            input_fields = []
            variables = []
            fields = request.form.getlist("field")
            labels = request.form.getlist("label")
            input_types = request.form.getlist("input_type")
            units = request.form.getlist("unit")

            print(f"Debug - Normal form fields from request: {fields}")

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

            form.input_types = input_fields
            form.variables = variables
            
            print(f"Debug - Updated normal form variables: {variables}")

        form.save()

        # Return HTMX response เพื่อปิด modal และรีเฟรช scope
        from flask import make_response
        import json
        import urllib.parse
        
        message = "บันทึกการแก้ไขสำเร็จ!"
        response = make_response('')  # Empty response
        
        # Encode ข้อความภาษาไทยให้เป็น URL encoded string
        encoded_message = urllib.parse.quote(message)
        
        # ปิด modal และแสดง toast
        trigger_data = {
            "closeModal": True,
            "showSuccess": encoded_message
        }
        response.headers['HX-Trigger'] = json.dumps(trigger_data)
        
        # รีเฟรช scope content
        response.headers['HX-Trigger-After-Swap'] = f'refreshScope{form.ghg_scope}'
        
        return response

    except Exception as e:
        import traceback
        traceback.print_exc()
        
        from flask import make_response
        response = make_response(f'<div class="alert alert-error"><span>Failed to update form: {str(e)}</span></div>')
        response.headers['HX-Retarget'] = '#modal-content'
        return response, 400


@module.route("/load-edit-form", methods=["GET"])
@login_required
@permissions_required_all(["แก้ไขฟอร์ม"])
def load_edit_form_and_formula():
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

        # บังคับไม่ใช้ cache โดยการ query ใหม่ทุกครั้ง
        form = FormAndFormula.objects(id=object_id).first()
        if not form:
            return render_template(
                "/form-management/edit-form-and-formula.html",
                form=None,
                error_msg="Form not found",
            )

        # แปลง FormAndFormula object เป็น dict เพื่อส่งไปยัง template
        # เพิ่ม timestamp เพื่อบังคับให้ browser ไม่ cache
        import time

        form_data = {
            "id": str(form.id),
            "material_name": form.material_name,
            "desc_form": form.desc_form,
            "desc_formula": form.desc_formula,
            "formula": form.formula,
            "formula2": form.formula2 or "",
            "ghg_scope": form.ghg_scope,
            "ghg_sup_scope": form.ghg_sup_scope,
            "is_linked": getattr(form, "is_linked", False),
            "linked_material_name": getattr(form, "linked_material_name", ""),
            "input_types": [],
            "_timestamp": int(time.time() * 1000),  # เพิ่ม timestamp
        }

        if form.input_types:
            for input_field in form.input_types:
                form_data["input_types"].append(
                    {
                        "field": input_field.field,
                        "label": input_field.label,
                        "input_type": input_field.input_type,
                        "unit": input_field.unit,
                    }
                )

        # เพิ่ม headers เพื่อป้องกัน cache
        from flask import make_response

        response = make_response(
            render_template(
                "/form-management/edit-form-and-formula.html", form=form_data
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


# อัปเดต add_form_and_formula function
@module.route("/add-form", methods=["POST"])
@login_required
def add_form_and_formula():
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
        is_linked = request.form.get("is_linked") == "true"
        linked_material_name = request.form.get("linked_material_name", "")

        print(f"Debug - is_linked: {is_linked}")
        print(f"Debug - linked_material_name: {linked_material_name}")
        print(f"Debug - form_type from request: {request.form.get('form_type')}")
        print(f"Debug - is_linked from request: {request.form.get('is_linked')}")

        # ตรวจสอบข้อมูลที่จำเป็น
        if not material_name or not formula or not ghg_scope or not ghg_sup_scope:
            missing_fields = []
            if not material_name:
                missing_fields.append("ชื่อวัสดุ")
            if not formula:
                missing_fields.append("สูตรคำนวณ")
            if not ghg_scope:
                missing_fields.append("Scope หลัก")
            if not ghg_sup_scope:
                missing_fields.append("Sub Scope")
            
            # ส่งคืนข้อความผิดพลาดแบบ HTMX
            from flask import make_response
            response = make_response(f'<div class="alert alert-error"><span>กรุณากรอกข้อมูลให้ครบถ้วน: {", ".join(missing_fields)}</span></div>')
            response.headers['HX-Retarget'] = '#modal-content'
            return response, 400

        # ตรวจสอบชื่อวัสดุซ้ำ
        existing_material = FormAndFormula.objects(material_name=material_name).first()
        if existing_material:
            from flask import make_response
            response = make_response(f'<div class="alert alert-error"><span>ชื่อวัสดุ "{material_name}" มีอยู่แล้ว กรุณาใช้ชื่ออื่น</span></div>')
            response.headers['HX-Retarget'] = '#modal-content'
            return response, 409

        try:
            ghg_sup_scope_int = int(ghg_sup_scope)
        except ValueError:
            from flask import make_response
            response = make_response('<div class="alert alert-error"><span>Sub Scope ต้องเป็นตัวเลขเท่านั้น</span></div>')
            response.headers['HX-Retarget'] = '#modal-content'
            return response, 400

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

        print(f"Debug - new_form.is_linked: {new_form.is_linked}")
        print(f"Debug - new_form.linked_material_name: {new_form.linked_material_name}")

        if is_linked and linked_material_name:
            # ดึงข้อมูล material ต้นฉบับ
            linked_material = FormAndFormula.objects(
                material_name=linked_material_name
            ).first()
            if not linked_material:
                from flask import make_response
                response = make_response(f'<div class="alert alert-error"><span>Material "{linked_material_name}" ไม่พบในระบบ</span></div>')
                response.headers['HX-Retarget'] = '#modal-content'
                return response, 404

            # ใช้ quantity_type ของ material ต้นฉบับ
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

            new_form.input_types = input_fields
            new_form.variables = variables
        else:
            # ฟอร์มปกติ - ดึงข้อมูล input fields จากฟอร์ม
            input_fields = []
            variables = []
            fields = request.form.getlist("field")
            labels = request.form.getlist("label")
            input_types = request.form.getlist("input_type")
            units = request.form.getlist("unit")

            print(f"Debug - Normal form fields: {fields}")

            for i in range(len(fields)):
                field = fields[i] if i < len(fields) else ""
                label = labels[i] if i < len(labels) else ""
                input_type = input_types[i] if i < len(input_types) else "text"
                unit = units[i] if i < len(units) else ""

                if field and input_type:
                    input_fields.append(
                        InputType.create_input(field, label, input_type, unit)
                    )
                    variables.append(field)

            new_form.input_types = input_fields
            new_form.variables = variables

        new_form.save()

        print(f"Debug - Saved form with is_linked: {new_form.is_linked}")

        # Return HTMX response เพื่อปิด modal และรีเฟรช scope
        from flask import make_response
        import json
        import urllib.parse
        
        message = "เพิ่มฟอร์มสำเร็จ!"
        response = make_response('')  # Empty response
        
        # Encode ข้อความภาษาไทยให้เป็น URL encoded string
        encoded_message = urllib.parse.quote(message)
        
        # ปิด modal และแสดง toast
        trigger_data = {
            "closeModal": True,
            "showSuccess": encoded_message
        }
        response.headers['HX-Trigger'] = json.dumps(trigger_data)
        
        # รีเฟรช scope content
        response.headers['HX-Trigger-After-Swap'] = f'refreshScope{ghg_scope}'
        
        return response

    except Exception as e:
        import traceback
        traceback.print_exc()
        
        from flask import make_response
        response = make_response(f'<div class="alert alert-error"><span>เกิดข้อผิดพลาด: {str(e)}</span></div>')
        response.headers['HX-Retarget'] = '#modal-content'
        return response, 400


@module.route("/get-form-data/<form_id>", methods=["GET"])
@login_required
def get_form_data(form_id):
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

        form_data = {
            "id": str(form.id),
            "material_name": form.material_name,
            "desc_form": form.desc_form,
            "desc_formula": form.desc_formula,
            "formula": form.formula,
            "formula2": form.formula2 or "",
            "ghg_scope": form.ghg_scope,
            "ghg_sup_scope": form.ghg_sup_scope,
            "is_linked": getattr(form, "is_linked", False),
            "linked_material_name": getattr(form, "linked_material_name", ""),
            "input_types": [],
        }

        if form.input_types:
            for input_field in form.input_types:
                form_data["input_types"].append(
                    {
                        "field": input_field.field,
                        "label": input_field.label,
                        "input_type": input_field.input_type,
                        "unit": input_field.unit,
                    }
                )

        return jsonify({"success": True, "form": form_data})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error loading form: {str(e)}"})


# เพิ่ม delete route
@module.route("/delete-form/<form_id>", methods=["DELETE"])
@login_required
def delete_form(form_id):
    try:
        from bson import ObjectId
        from bson.errors import InvalidId

        try:
            object_id = ObjectId(form_id)
        except InvalidId:
            return jsonify({"success": False, "message": "Invalid form ID format"}), 400
        form = FormAndFormula.objects(id=object_id).first()
        if not form:
            return jsonify({"success": False, "message": "Form not found"}), 404
        form_name = form.material_name  # ใช้ชื่อวัสดุแทน
        form.delete()
        return jsonify(
            {"success": True, "message": f"Form '{form_name}' deleted successfully"}
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return (
            jsonify({"success": False, "message": f"Error deleting form: {str(e)}"}),
            500,
        )


@module.route("/get-available-materials-by-scope/<int:scope>/<int:sub_scope>", methods=["GET"])
@login_required
def get_available_materials_by_scope(scope, sub_scope):
    """
    ดึงรายชื่อ material ที่สามารถลิงก์ได้ตาม scope (ฟังก์ชันเก่า - อาจไม่ใช้แล้ว)
    """
    try:
        # ดึง material ที่ไม่ใช่ฟอร์มลิงก์ในกลุ่มเดียวกัน
        available_form = FormAndFormula.objects()

        return render_template(
            "form-management/partials/material-select.html",
            available_form=available_form,
        )

    except Exception as e:
        return f'<option value="">Error: {str(e)}</option>'


@module.route("/get-linked-material-data/<material_name>", methods=["GET"])
@login_required
def get_linked_material_data(material_name):
    """
    ดึงข้อมูล input types ของ material ต้นฉบับสำหรับฟอร์มลิงก์
    """
    try:
        form = FormAndFormula.objects(material_name=material_name).first()
        if not form:
            return jsonify({"error": "Material not found"}), 404

        input_types = []
        for input_type in form.input_types:
            input_types.append(
                {
                    "field": input_type.field,
                    "label": input_type.label,
                    "input_type": input_type.input_type,
                    "unit": input_type.unit,
                }
            )

        return jsonify(
            {
                "material_name": form.material_name,
                "ghg_scope": form.ghg_scope,
                "ghg_sup_scope": form.ghg_sup_scope,
                "input_types": input_types,
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Scope Management Routes
@module.route("/get-scope-content", methods=["GET"])
@login_required
def get_scope_content():
    """โหลด content ตาม scope ที่เลือก - แทน JavaScript scope switching"""
    try:
        active_scope = request.args.get('active_scope', '1')
        
        # โหลดข้อมูลใหม่
        forms = FormAndFormula.objects().order_by(
            "ghg_scope", "ghg_sup_scope", "material_name"
        )
        
        scopes = Scope.objects().order_by("ghg_scope", "ghg_sup_scope")
        scope_names = {}
        for scope in scopes:
            key = f"{scope.ghg_scope}.{scope.ghg_sup_scope}"
            scope_names[key] = scope.ghg_name
        
        # เลือก template ตาม scope
        if active_scope == '1':
            template_name = "form-management/partials/scope1-content.html"
        elif active_scope == '2':
            template_name = "form-management/partials/scope2-content.html"  
        elif active_scope == '3':
            template_name = "form-management/partials/scope3-content.html"
        else:
            template_name = "form-management/partials/scope1-content.html"
        
        return render_template(
            template_name,
            forms=forms,
            scope_names=scope_names,
            active_scope=active_scope
        )
    except Exception as e:
        return f'<div class="text-error">Error loading scope content: {str(e)}</div>'

@module.route("/scope/1", methods=["GET"])
@login_required  
def get_scope1():
    """โหลด Scope 1 content พร้อมการกรอง Sub Scope"""
    forms = FormAndFormula.objects().order_by("ghg_scope", "ghg_sup_scope", "material_name")
    scopes = Scope.objects().order_by("ghg_scope", "ghg_sup_scope")
    scope_names = {}
    for scope in scopes:
        key = f"{scope.ghg_scope}.{scope.ghg_sup_scope}"
        scope_names[key] = scope.ghg_name
    
    # รับพารามิเตอร์การกรอง
    filter_sub_scope = request.args.get('filter_sub_scope')
    show_all = request.args.get('show_all', 'false').lower() == 'true'
    
    return render_template(
        "form-management/partials/scope1-content.html",
        forms=forms,
        scope_names=scope_names,
        active_scope="1",
        filter_sub_scope=int(filter_sub_scope) if filter_sub_scope else None,
        show_all=show_all
    )

@module.route("/scope/2", methods=["GET"])
@login_required
def get_scope2():
    """โหลด Scope 2 content พร้อมการกรอง Sub Scope"""
    forms = FormAndFormula.objects().order_by("ghg_scope", "ghg_sup_scope", "material_name")
    scopes = Scope.objects().order_by("ghg_scope", "ghg_sup_scope")
    scope_names = {}
    for scope in scopes:
        key = f"{scope.ghg_scope}.{scope.ghg_sup_scope}"
        scope_names[key] = scope.ghg_name
    
    # รับพารามิเตอร์การกรอง
    filter_sub_scope = request.args.get('filter_sub_scope')
    show_all = request.args.get('show_all', 'false').lower() == 'true'
    
    return render_template(
        "form-management/partials/scope2-content.html", 
        forms=forms,
        scope_names=scope_names,
        active_scope="2",
        filter_sub_scope=int(filter_sub_scope) if filter_sub_scope else None,
        show_all=show_all
    )

@module.route("/scope/3", methods=["GET"])
@login_required
def get_scope3():
    """โหลด Scope 3 content พร้อมการกรอง Sub Scope"""
    forms = FormAndFormula.objects().order_by("ghg_scope", "ghg_sup_scope", "material_name")
    scopes = Scope.objects().order_by("ghg_scope", "ghg_sup_scope")
    scope_names = {}
    for scope in scopes:
        key = f"{scope.ghg_scope}.{scope.ghg_sup_scope}"
        scope_names[key] = scope.ghg_name
    
    # รับพารามิเตอร์การกรอง
    filter_sub_scope = request.args.get('filter_sub_scope')
    show_all = request.args.get('show_all', 'false').lower() == 'true'
    
    return render_template(
        "form-management/partials/scope3-content.html",
        forms=forms, 
        scope_names=scope_names,
        active_scope="3",
        filter_sub_scope=int(filter_sub_scope) if filter_sub_scope else None,
        show_all=show_all
    )

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


@module.route("/show-toast/<message_type>", methods=["GET"])
@login_required
def show_toast(message_type):
    """แสดง toast notification - Pure Python"""
    message = request.args.get('message', 'สำเร็จ!')
    
    # กำหนดสีและไอคอนตามประเภท
    if message_type == 'success':
        bg_color = 'bg-green-500'
        icon = 'check-circle'
    elif message_type == 'error':
        bg_color = 'bg-red-500'
        icon = 'alert-circle'
    elif message_type == 'warning':
        bg_color = 'bg-yellow-500'
        icon = 'alert-triangle'
    else:
        bg_color = 'bg-blue-500'
        icon = 'info'
    
    toast_html = f'''
    <div id="toast-notification" class="fixed top-4 right-4 z-50 {bg_color} text-white px-6 py-3 rounded-lg shadow-lg max-w-sm transform transition-all duration-300 translate-x-0">
        <div class="flex items-center gap-2">
            <i data-feather="{icon}" class="w-5 h-5"></i>
            <span class="text-sm font-medium">{message}</span>
            <button onclick="this.parentElement.parentElement.remove()" class="ml-2 text-white hover:text-gray-200">
                <i data-feather="x" class="w-4 h-4"></i>
            </button>
        </div>
    </div>
    <script>
        // Auto hide after 3 seconds
        setTimeout(function() {{
            const toast = document.getElementById('toast-notification');
            if (toast) {{
                toast.classList.add('translate-x-full');
                setTimeout(function() {{
                    if (toast.parentNode) {{
                        toast.remove();
                    }}
                }}, 300);
            }}
        }}, 3000);
        
        // Initialize feather icons
        if (typeof feather !== 'undefined') {{
            feather.replace();
        }}
    </script>
    '''
    
    return toast_html


@module.route("/close-modal-and-refresh", methods=["GET"])
@login_required  
def close_modal_and_refresh():
    """ปิด modal และรีเฟรช scope content - Pure Python"""
    scope = request.args.get('scope', '1')
    message = request.args.get('message', 'บันทึกสำเร็จ!')
    
    # สร้าง response HTML ที่จะ:
    # 1. ปิด modal
    # 2. แสดง toast
    # 3. รีเฟรช scope content
    
    response_html = f'''
    <div hx-trigger="load" 
         hx-get="/form-management/scope/{scope}"
         hx-target="#scope-content-area"
         hx-swap="innerHTML">
    </div>
    
    <div hx-trigger="load delay:100ms"
         hx-get="/form-management/show-toast/success?message={message}"
         hx-target="body"
         hx-swap="beforeend">
    </div>
    
    <script>
        // ปิด modal
        const modal = document.getElementById('modal');
        if (modal) {{
            modal.classList.remove('modal-open');
        }}
    </script>
    '''
    
    return response_html
