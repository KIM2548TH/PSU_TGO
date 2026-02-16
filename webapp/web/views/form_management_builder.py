"""
Form Builder - สร้างและแก้ไขฟอร์ม
รวม Calculator, Form Builder, Linked Fields
"""
from flask import Blueprint, render_template, request
from flask_login import login_required
from ...models import FormAndFormula
from bson import ObjectId

# Sub-blueprint ของ form_management
# Parent มี prefix: /form-management
# Child มี prefix: /form-builder
# รวมกัน: /form-management/form-builder/*
module = Blueprint("form_builder", __name__, url_prefix="/form-builder")


# ============================================
# CALCULATOR ROUTES - สำหรับสร้างสูตร
# ============================================

@module.route("/calculator/load-variables", methods=["POST"])
@login_required
def calculator_load_variables():
    """โหลด variable buttons สำหรับ calculator"""
    try:
        form_data = request.form.to_dict()
        variables = _get_calculator_variables(form_data)
        
        # ใช้ calculator-variables.html เดิมหรือส่งกลับ HTML โดยตรง
        return render_template(
            "form-management/partials/calculator-variables.html",
            variables=variables
        )
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/calculator/show", methods=["POST"])
@login_required
def calculator_show():
    """แสดง calculator dropdown"""
    try:
        form_data = request.form.to_dict()
        variables = _get_calculator_variables(form_data)
        
        return render_template(
            "form-management/partials/unified-calculator.html",
            calculator_type="formula",
            variables=variables
        )
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/calculator/hide", methods=["POST"])
@login_required
def calculator_hide():
    """ปิด calculator"""
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
            "form-management/partials/unified-formula-input.html",
            input_type="formula",
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
            "form-management/partials/unified-formula-input.html",
            input_type="formula",
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
            "form-management/partials/unified-formula-input.html",
            input_type="formula",
            formula_value=""
        )
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


# ============================================
# FORM BUILDER ROUTES - สำหรับสร้าง Input Fields
# ============================================

@module.route("/add-input-field", methods=["POST"])
@login_required
def add_input_field():
    """เพิ่ม input field ใหม่ (รองรับทั้ง normal form และ linked form)"""
    try:
        field_index = request.form.get('field_index', 0)
        field_number = int(field_index) + 1
        is_linked_form = request.form.get('is_linked_form', 'false') == 'true'
        
        return render_template(
            "form-management/partials/input-field-row.html",
            field_index=field_index,
            field_number=field_number,
            is_linked_form=is_linked_form
        )
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/remove-input-field", methods=["DELETE"])
@login_required
def remove_input_field():
    """ลบ input field"""
    return "", 200


@module.route("/toggle-form-type", methods=["POST"])
@login_required
def toggle_form_type():
    """สลับระหว่างฟอร์มปกติกับฟอร์มลิงก์"""
    try:
        form_type = request.form.get('form_type', 'normal')
        
        if form_type == 'linked':
            # ดึงรายการ material ที่สามารถลิงก์ได้
            materials = FormAndFormula.objects().order_by("ghg_scope", "ghg_sup_scope", "material_name")
            return render_template(
                "form-management/partials/linked-form-section.html",
                materials=materials
            )
        else:
            return render_template(
                "form-management/partials/normal-form-section.html"
            )
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/material-selector", methods=["GET"])
@login_required
def material_selector():
    """แสดง Material Selector Modal"""
    try:
        # ดึงรายการ material ที่สามารถลิงก์ได้
        materials = FormAndFormula.objects().order_by("ghg_scope", "ghg_sup_scope", "material_name")
        return render_template(
            "form-management/partials/material-selector-modal.html",
            materials=materials
        )
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/search-materials", methods=["GET"])
@login_required
def search_materials():
    """ค้นหา Material สำหรับลิงก์"""
    try:
        search_term = request.args.get('material_search', '').lower().strip()
        selected_ids_str = request.args.get('selected_ids', '')  # เพิ่ม: รับ selected IDs
        
        # Parse selected IDs
        selected_ids = []
        if selected_ids_str:
            try:
                import json
                selected_ids = json.loads(selected_ids_str)
            except:
                selected_ids = [sid.strip() for sid in selected_ids_str.split(',') if sid.strip()]
        
        # ดึงรายการ material ที่สามารถลิงก์ได้
        materials_query = FormAndFormula.objects().order_by("ghg_scope", "ghg_sup_scope", "material_name")
        
        # Filter by search term
        if search_term:
            filtered_materials = []
            for material in materials_query:
                # Search in material name, description
                searchable = f"{material.material_name} {material.desc_form or ''} Scope {material.ghg_scope}.{material.ghg_sup_scope}".lower()
                if search_term in searchable:
                    filtered_materials.append(material)
            materials = filtered_materials
        else:
            materials = list(materials_query)
        
        return render_template(
            "form-management/partials/material-search-results.html",
            materials=materials,
            selected_ids=selected_ids
        )
    except Exception as e:
        return f'<div class="text-error p-4">Error: {str(e)}</div>'


@module.route("/select-material", methods=["POST"])
@login_required
def select_material():
    """เลือก Material และโหลดฟิลด์"""
    try:
        material_name = request.form.get('material_name')
        scope = request.form.get('scope')
        
        if not material_name:
            return '<div class="text-error">No material selected</div>'
        
        # Return selected display + trigger to load fields
        response = render_template(
            "form-management/partials/selected-material-display.html",
            material_name=material_name,
            scope=scope
        )
        
        # Add HX-Trigger to load linked fields
        # Note: Don't pass Thai text in headers (causes UnicodeEncodeError)
        # The event listener will get the material name from the hidden input
        from flask import make_response
        resp = make_response(response)
        resp.headers['HX-Trigger-After-Settle'] = '{"loadLinkedFields": {}}'
        
        return resp
        
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/clear-material-selection", methods=["POST"])
@login_required
def clear_material_selection():
    """ล้างการเลือก Material"""
    return ''


@module.route("/load-multiple-linked-fields", methods=["GET"])
@login_required  
def load_multiple_linked_fields():
    """โหลดฟิลด์จากหลาย linked materials พร้อม checkbox ให้เลือก"""
    from bson import ObjectId
    
    form_ids_str = request.args.get('form_ids', '')
    editing_form_id = request.args.get('editing_form_id', '')  # เพิ่ม: ID ของฟอร์มที่กำลังแก้ไข
    
    if not form_ids_str:
        return '<div class="text-center text-gray-500">กรุณาเลือก Material</div>'
    
    form_ids = [fid.strip() for fid in form_ids_str.split(',') if fid.strip()]
    if not form_ids:
        return '<div class="text-center text-gray-500">กรุณาเลือก Material</div>'
    
    # ถ้ากำลังแก้ไข ให้ดึง is_used จาก database
    existing_is_used = {}
    if editing_form_id:
        try:
            editing_form = FormAndFormula.objects(id=ObjectId(editing_form_id)).first()
            if editing_form and editing_form.input_types:
                for input_type in editing_form.input_types:
                    source_id = getattr(input_type, 'source_form_id', None)
                    original_field = getattr(input_type, 'original_field', input_type.field)
                    if source_id:
                        key = f"{original_field}_{source_id}"
                        existing_is_used[key] = getattr(input_type, 'is_used', True)
                        print(f"🔍 MULTI LOAD: existing key={key}, is_used={existing_is_used[key]}")
        except Exception as e:
            print(f"🔍 MULTI LOAD: Error loading editing form: {e}")
    
    all_fields = []
    
    for form_id in form_ids:
        try:
            linked_form = FormAndFormula.objects(id=ObjectId(form_id)).first()
        except:
            continue
            
        if not linked_form or not linked_form.input_types:
            continue
        
        # Add fields with source info - ใช้ชื่อฟิลด์ต้นฉบับ
        for input_type in linked_form.input_types:
            # สร้าง field_identifier สำหรับเช็ค (field_formid)
            field_identifier = f"{input_type.field}_{form_id}"
            
            all_fields.append({
                'field': input_type.field,  # ชื่อฟิลด์ต้นฉบับ
                'field_identifier': field_identifier,  # ใช้สำหรับ checkbox value
                'label': input_type.label,  # label ต้นฉบับ
                'input_type': input_type.input_type,
                'unit': input_type.unit,
                'source_form_id': form_id,
                'source_form_name': linked_form.material_name
            })
    
    if not all_fields:
        return '<div class="text-center text-gray-500">ไม่พบฟิลด์จาก Materials ที่เลือก</div>'
    
    # Render fields with checkboxes
    html = f'<div class="text-sm text-gray-700 mb-3 flex items-center gap-2"><i data-feather="info" class="w-4 h-4 text-blue-500"></i>พบ <strong>{len(all_fields)}</strong> ฟิลด์จาก <strong>{len(form_ids)}</strong> Material - เลือกฟิลด์ที่ต้องการใช้</div>'
    html += '<div class="space-y-2 max-h-80 overflow-y-auto">'
    
    for field in all_fields:
        # ตรวจสอบว่าควรติ๊กหรือไม่
        if editing_form_id:
            # ถ้ากำลังแก้ไข ใช้ค่าจาก database
            is_checked = existing_is_used.get(field['field_identifier'], True)
        else:
            # ถ้าสร้างใหม่ ติ๊กหมดเป็น default
            is_checked = True
        
        checked_attr = 'checked' if is_checked else ''
        print(f"🔍 MULTI HTML: field_identifier={field['field_identifier']}, is_checked={is_checked}, checked_attr='{checked_attr}'")
        
        html += f'''
        <div class="flex items-start gap-3 p-3 bg-white border border-gray-200 rounded-lg hover:bg-blue-50 transition-colors">
          <input type="checkbox" 
                 name="linked_field_used"
                 class="checkbox checkbox-sm checkbox-primary mt-1" 
                 {checked_attr}
                 value="{field['field_identifier']}">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <i data-feather="link" class="w-3 h-3 text-blue-600 flex-shrink-0"></i>
              <span class="text-sm font-medium text-gray-900">{field['label']}</span>
            </div>
            <div class="flex items-center gap-2 mt-1">
              <span class="text-xs text-gray-500 font-mono">{field['field']}</span>
              <span class="text-xs text-gray-400">• {field['input_type']}</span>
              {f'<span class="text-xs text-gray-400">• {field["unit"]}</span>' if field['unit'] else ''}
              <span class="text-xs text-blue-600">• จาก: {field['source_form_name']}</span>
            </div>
          </div>
        </div>
        '''
    
    html += '</div>'
    html += '''
    <script>
    if (typeof feather !== 'undefined') feather.replace();
    </script>
    '''
    
    return html


@module.route("/load-linked-fields", methods=["GET"])  
@login_required
def load_linked_fields():
    """โหลดฟิลด์ของ linked material (single - backward compatibility)"""
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


@module.route("/load-edit-fields", methods=["GET"])
@login_required
def load_edit_fields():
    """โหลด input fields สำหรับ edit form - แยกฟิลด์ลิงก์กับฟิลด์ของตัวเอง"""
    try:
        form_id = request.args.get('form_id')
        
        if not form_id:
            return render_template("form-management/partials/normal-form-section.html")
        
        form_obj = FormAndFormula.objects(id=ObjectId(form_id)).first()
        
        if not form_obj or not form_obj.input_types:
            return render_template("form-management/partials/normal-form-section.html")
        
        # แยกฟิลด์ออกเป็น 2 ประเภท
        linked_fields = []  # ฟิลด์จาก linked forms
        custom_fields = []  # ฟิลด์ของตัวเอง
        
        for input_type in form_obj.input_types:
            source_id = getattr(input_type, 'source_form_id', None)
            if source_id:
                # ฟิลด์ลิงก์
                linked_fields.append(input_type)
            else:
                # ฟิลด์ของตัวเอง
                custom_fields.append(input_type)
        
        # สร้าง HTML สำหรับฟิลด์ของตัวเอง
        custom_fields_html = []
        for i, input_type in enumerate(custom_fields):
            field_html = f'''
            <div class="border border-gray-300 rounded-xl p-4 bg-gray-50 shadow-sm" data-index="input-{i}">
                <div class="flex justify-between items-center mb-3">
                    <h4 class="text-md font-semibold text-gray-600">Field #{i + 1}</h4>
                    <button type="button" class="btn btn-sm btn-error"
                            hx-delete="/form-management/form-builder/remove-input-field"
                            hx-target="closest [data-index]"
                            hx-swap="delete"
                            hx-confirm="ต้องการลบฟิลด์นี้หรือไม่?"
                            onclick="updateFieldCounter()">✕</button>
                </div>
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                        <label class="text-sm text-gray-600">Field Name</label>
                        <input name="field" class="input input-bordered w-full mt-1" 
                               placeholder="field_name" value="{input_type.field}" required>
                    </div>
                    <div>
                        <label class="text-sm text-gray-600">Label</label>
                        <input name="label" class="input input-bordered w-full mt-1" 
                               placeholder="Display Label" value="{input_type.label}">
                    </div>
                    <div>
                        <label class="text-sm text-gray-600">Input Type</label>
                        <select name="input_type" class="select select-bordered w-full mt-1">
                            <option value="number" {"selected" if input_type.input_type == "number" else ""}>Number</option>
                            <option value="text" {"selected" if input_type.input_type == "text" else ""}>Text</option>
                            <option value="select" {"selected" if input_type.input_type == "select" else ""}>Select</option>
                        </select>
                    </div>
                    <div>
                        <label class="text-sm text-gray-600">Unit</label>
                        <input name="unit" class="input input-bordered w-full mt-1" 
                               placeholder="kg, liter, etc." value="{input_type.unit or ''}">
                    </div>
                </div>
            </div>
            '''
            custom_fields_html.append(field_html)
        
        complete_html = f'''
        <div id="input-fields-container" class="space-y-3">
            {"".join(custom_fields_html)}
        </div>
        
        <button type="button" class="btn btn-sm btn-outline btn-primary w-full mt-3"
                hx-post="/form-management/form-builder/add-input-field"
                hx-target="#input-fields-container"
                hx-swap="beforeend"
                hx-vals='{{"field_index": "{len(custom_fields)}", "is_linked_form": "false"}}'
                onclick="updateFieldCounter()">
            <i data-feather="plus" class="w-4 h-4 mr-1"></i>
            เพิ่มฟิลด์ใหม่
        </button>
        '''
        
        return complete_html
    except Exception as e:
        return f'<div class="text-error">Error loading edit fields: {str(e)}</div>'


@module.route("/load-edit-linked-fields", methods=["GET"])
@login_required
def load_edit_linked_fields():
    """โหลดฟิลด์จาก linked forms สำหรับ edit - แสดงสถานะ checkbox จากฐานข้อมูล"""
    try:
        form_id = request.args.get('form_id')
        
        if not form_id:
            return '<div class="text-center text-gray-500">ไม่พบฟอร์ม</div>'
        
        form_obj = FormAndFormula.objects(id=ObjectId(form_id)).first()
        
        if not form_obj or not form_obj.input_types:
            return '<div class="text-center text-gray-500">ไม่มีฟิลด์</div>'
        
        # ดึง linked fields พร้อมสถานะ is_used จากฐานข้อมูล
        linked_fields_with_info = []
        
        # รวบรวม source_form_ids ที่ต้อง query
        source_form_ids = set()
        for input_type in form_obj.input_types:
            source_id = getattr(input_type, 'source_form_id', None)
            if source_id:
                source_form_ids.add(source_id)
        
        # Query source forms ทีเดียว
        source_forms_map = {}
        if source_form_ids:
            try:
                source_forms = FormAndFormula.objects(id__in=[ObjectId(sid) for sid in source_form_ids]).only('id', 'material_name')
                source_forms_map = {str(f.id): f.material_name for f in source_forms}
            except:
                pass
        
        # สร้าง linked fields info
        for input_type in form_obj.input_types:
            source_id = getattr(input_type, 'source_form_id', None)
            is_used = getattr(input_type, 'is_used', True)
            original_field = getattr(input_type, 'original_field', input_type.field)
            
            print(f"🔍 LOAD DEBUG: field={input_type.field}, source_id={source_id}, is_used={is_used}, original_field={original_field}")
            
            if source_id:  # เฉพาะ linked fields
                source_form_name = source_forms_map.get(source_id, "Unknown")
                
                linked_fields_with_info.append({
                    'field': input_type.field,
                    'label': input_type.label,
                    'input_type': input_type.input_type,
                    'unit': input_type.unit,
                    'source_form_id': source_id,
                    'source_form_name': source_form_name,
                    'is_used': is_used,
                    'original_field': original_field,
                    'field_identifier': f"{original_field}_{source_id}"
                })
                
                print(f"🔍 LOAD DEBUG: Added linked field - identifier={original_field}_{source_id}, is_used={is_used}")
        
        if not linked_fields_with_info:
            return '<div class="text-center text-gray-500">ไม่มี linked fields</div>'
        
        # สร้าง HTML พร้อม checkbox ตามสถานะ
        html = f'<div class="text-sm text-gray-700 mb-3 flex items-center gap-2"><i data-feather="info" class="w-4 h-4 text-blue-500"></i>พบ <strong>{len(linked_fields_with_info)}</strong> ฟิลด์จาก linked materials</div>'
        html += '<div class="space-y-2 max-h-80 overflow-y-auto">'
        
        for field in linked_fields_with_info:
            checked = 'checked' if field['is_used'] else ''
            print(f"🔍 HTML DEBUG: field_identifier={field['field_identifier']}, is_used={field['is_used']}, checked_attr='{checked}'")
            
            html += f'''
            <div class="flex items-start gap-3 p-3 bg-white border border-gray-200 rounded-lg hover:bg-blue-50 transition-colors">
              <input type="checkbox" 
                     name="linked_field_used"
                     class="checkbox checkbox-sm checkbox-primary mt-1" 
                     {checked}
                     value="{field['field_identifier']}">
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <i data-feather="link" class="w-3 h-3 text-blue-600 flex-shrink-0"></i>
                  <span class="text-sm font-medium text-gray-900">{field['label']}</span>
                </div>
                <div class="flex items-center gap-2 mt-1">
                  <span class="text-xs text-gray-500 font-mono">{field['field']}</span>
                  <span class="text-xs text-gray-400">• {field['input_type']}</span>
                  {f'<span class="text-xs text-gray-400">• {field["unit"]}</span>' if field['unit'] else ''}
                  <span class="text-xs text-blue-600">• จาก: {field['source_form_name']}</span>
                </div>
              </div>
            </div>
            '''
        
        html += '</div>'
        html += '''
        <script>
        if (typeof feather !== 'undefined') feather.replace();
        </script>
        '''
        
        return html
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/load-edit-custom-fields", methods=["GET"])
@login_required
def load_edit_custom_fields():
    """โหลด custom fields (ฟิลด์ที่ไม่ได้ลิงก์) สำหรับ edit"""
    try:
        form_id = request.args.get('form_id')
        
        if not form_id:
            return '<div class="space-y-3"></div>'
        
        form_obj = FormAndFormula.objects(id=ObjectId(form_id)).first()
        
        if not form_obj or not form_obj.input_types:
            return '<div class="space-y-3"></div>'
        
        # ดึงเฉพาะ custom fields (ไม่มี source_form_id)
        custom_fields = []
        for input_type in form_obj.input_types:
            source_id = getattr(input_type, 'source_form_id', None)
            if not source_id:  # Custom field
                custom_fields.append(input_type)
        
        if not custom_fields:
            return '<div class="space-y-3"></div>'
        
        # สร้าง HTML สำหรับ custom fields
        custom_fields_html = []
        for i, input_type in enumerate(custom_fields):
            field_html = f'''
            <div class="border border-amber-300 rounded-xl p-4 bg-white shadow-sm" data-index="input-{i}">
                <div class="flex justify-between items-center mb-3">
                    <h4 class="text-md font-semibold text-amber-700">Custom Field #{i + 1}</h4>
                    <button type="button" class="btn btn-sm btn-error"
                            hx-delete="/form-management/form-builder/remove-input-field"
                            hx-target="closest [data-index]"
                            hx-swap="delete"
                            hx-confirm="ต้องการลบฟิลด์นี้หรือไม่?">✕</button>
                </div>
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                        <label class="text-sm text-gray-600">Field Name</label>
                        <input name="custom_field" class="input input-bordered w-full mt-1" 
                               placeholder="field_name" value="{input_type.field}" required>
                    </div>
                    <div>
                        <label class="text-sm text-gray-600">Label</label>
                        <input name="custom_label" class="input input-bordered w-full mt-1" 
                               placeholder="Display Label" value="{input_type.label}" required>
                    </div>
                    <div>
                        <label class="text-sm text-gray-600">Input Type</label>
                        <select name="custom_input_type" class="select select-bordered w-full mt-1">
                            <option value="number" {"selected" if input_type.input_type == "number" else ""}>Number</option>
                            <option value="text" {"selected" if input_type.input_type == "text" else ""}>Text</option>
                            <option value="select" {"selected" if input_type.input_type == "select" else ""}>Select</option>
                        </select>
                    </div>
                    <div>
                        <label class="text-sm text-gray-600">Unit</label>
                        <input name="custom_unit" class="input input-bordered w-full mt-1" 
                               placeholder="kg, liter, etc." value="{input_type.unit or ''}">
                    </div>
                </div>
            </div>
            '''
            custom_fields_html.append(field_html)
        
        return '<div class="space-y-3">' + "".join(custom_fields_html) + '</div>'
        
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/get-available-materials", methods=["GET"])
@login_required
def get_available_materials():
    """ดึงรายชื่อ material ที่สามารถลิงก์ได้"""
    try:
        available_form = FormAndFormula.objects().order_by("ghg_scope", "ghg_sup_scope", "material_name")
        
        return render_template(
            "form-management/partials/material-select.html",
            available_form=available_form,
        )
    except Exception as e:
        return f'<div class="text-red-500">Error: {str(e)}</div>'


# ============================================
# HELPER FUNCTIONS
# ============================================

def _get_calculator_variables(form_data):
    """ดึง variables สำหรับ calculator"""
    variables = []
    form_type = form_data.get('form_type', 'normal')
    
    if form_type == 'linked':
        # 1. Variables from Linked Forms
        # Get linked_forms array (could be JSON string or list)
        linked_forms_data = form_data.get('linked_forms')
        if linked_forms_data:
            import json
            try:
                # Parse JSON if it's a string
                if isinstance(linked_forms_data, str):
                    linked_form_ids = json.loads(linked_forms_data) if linked_forms_data else []
                else:
                    linked_form_ids = linked_forms_data
                
                # Load variables from all linked forms
                # Get checked fields from request
                linked_fields_used = request.form.getlist('linked_field_used')
                
                for form_id in linked_form_ids:
                    linked_form = FormAndFormula.objects(id=form_id).first()
                    if linked_form and linked_form.input_types:
                        for input_type in linked_form.input_types:
                            # Filter unchecked fields
                            # field_identifier must match what is used in checkbox (load_multiple_linked_fields)
                            field_identifier = f"{input_type.field}_{linked_form.id}"
                            
                            # If linked_fields_used is present (not empty), filter.
                            # If empty/None, it might mean nothing is checked, or it's a first load. 
                            # But usually calculator is opened after selecting fields.
                            # If request.form has keys but not linked_field_used, it means all unchecked.
                            if 'linked_field_used' in request.form and field_identifier not in linked_fields_used:
                                continue

                            # Logic เดียวกันกับ form_management_view.py -> _setup_linked_form_fields (Daisy Chain)
                            # เพื่อให้ชื่อตัวแปรใน Calculator ตรงกับที่บันทึกลง Database
                            
                            # Daisy Chain Naming Strategy: RootBase_CurrentMaterialName
                            # 1. Determine Base Name (Root)
                            if getattr(input_type, 'source_form_id', None):
                                # ถ้าแม่เป็น Linked Field แสดงว่าแม่มี Suffix -> เราต้องตัดออกเพื่อหา Base
                                base_name = input_type.field.rpartition('_')[0]
                                if not base_name:
                                     base_name = input_type.field
                            else:
                                # ถ้าแม่เป็น Original Field -> ใช้ชื่อแม่เป็น Base ได้เลย
                                base_name = input_type.field
                            
                            # 2. สร้าง Field Name ใหม่
                            field_name = f"{base_name}_{linked_form.material_name}"
                            
                            # 3. สร้าง Label ใหม่
                            base_label = input_type.label.split('(')[0].strip()
                            
                            variables.append({
                                'field': field_name,
                                'label': f"{base_label} ({linked_form.material_name})",
                                'color': 'bg-pink-100 text-pink-800'
                            })
            except Exception as e:
                print(f"Error loading linked variables: {e}")
                pass
        
        # 2. Variables from Custom Fields (Fields added manually to this linked form)
        custom_fields = form_data.getlist('custom_field') if hasattr(form_data, 'getlist') else request.form.getlist('custom_field') or []
        custom_labels = form_data.getlist('custom_label') if hasattr(form_data, 'getlist') else request.form.getlist('custom_label') or []
        
        for i, field in enumerate(custom_fields):
            if field:
                label = custom_labels[i] if i < len(custom_labels) else field
                variables.append({
                    'field': field,
                    'label': f"{label} (Custom)",
                    'color': 'bg-green-100 text-green-800'
                })
                
    else:
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
