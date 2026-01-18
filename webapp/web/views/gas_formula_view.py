import datetime

from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, render_template, request, jsonify, make_response
from flask_login import login_required, current_user

from ...models import FormAndFormula, Material
from ...services.user_service import UserService
from ..utils.acl import permissions_required_all
from ..utils.toast_utils import success_response, error_response

module = Blueprint("gas_formula", __name__, url_prefix="/gas-formula")


# === CONVERSION FORMULA ROUTES ===
@module.route("/load-conversion-formula-editor/<form_id>", methods=["GET"])
@login_required
def load_conversion_formula_editor(form_id):
    """โหลดหน้าแก้ไขสูตรแปลงหน่วย"""
    try:
        form_obj = FormAndFormula.objects(id=ObjectId(form_id)).first()
        if not form_obj:
            return render_template("form-management/conversion-formula-editor.html", 
                             form=None, 
                             error_msg="Form not found")
        
        return render_template("form-management/conversion-formula-editor.html", form=form_obj)
        
    except InvalidId:
        return render_template("form-management/conversion-formula-editor.html", 
                         form=None, 
                         error_msg="Invalid form ID")
    except Exception as e:
        return render_template("form-management/conversion-formula-editor.html", 
                         form=None, 
                         error_msg=f"Error loading form: {str(e)}")


@module.route("/save-conversion-formulas/<form_id>", methods=["POST"])
@login_required
@permissions_required_all(["แก้ไขฟอร์ม"])
def save_conversion_formulas(form_id):
    """บันทึกสูตรแปลงหน่วย"""
    try:
        # ตรวจสอบว่า form_id เป็น ObjectId ที่ถูกต้องหรือไม่
        try:
            ObjectId(form_id)
        except InvalidId:
            return error_response("Form ID ไม่ถูกต้อง")
        
        form_obj = FormAndFormula.objects(id=ObjectId(form_id)).first()
        if not form_obj:
            return error_response("ไม่พบฟอร์มที่ต้องการ")
        
        # อัปเดตสูตรแปลงหน่วย
        form_obj.formula = request.form.get("formula", "")
        form_obj.formula2 = request.form.get("formula2", "")
        form_obj.desc_formula = request.form.get("desc_formula", "")
        form_obj.desc_formula2 = request.form.get("desc_formula2", "")
        form_obj.save()
        
        # อัปเดต Material ทั้งหมดที่ใช้ฟอร์มนี้
        _update_materials_with_new_formulas(form_obj)
        
        return success_response(
            "บันทึกสูตรแปลงหน่วยสำเร็จ!",
            closeModal=True,
            refreshAllScopes={"scope": str(form_obj.ghg_scope)},
            refreshScopeContent={"scope": str(form_obj.ghg_scope)},
            updateActiveScopeCard={"scope": str(form_obj.ghg_scope)},
            **{f"refreshScope{form_obj.ghg_scope}": True}
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return error_response(f"เกิดข้อผิดพลาด: {str(e)}")


# === GAS FORMULA ROUTES ===
@module.route("/load-gas-formula-editor/<form_id>", methods=["GET"])
@login_required
def load_gas_formula_editor(form_id):
    """โหลดหน้าแก้ไขสูตรก๊าซ"""
    try:
        form_obj = FormAndFormula.objects(id=ObjectId(form_id)).first()
        if not form_obj:
            return render_template("form-management/gas-formula-editor.html", 
                             form=None, 
                             error_msg="Form not found")
        
        return render_template("form-management/gas-formula-editor.html", form=form_obj)
        
    except InvalidId:
        return render_template("form-management/gas-formula-editor.html", 
                         form=None, 
                         error_msg="Invalid form ID")
    except Exception as e:
        return render_template("form-management/gas-formula-editor.html", 
                         form=None, 
                         error_msg=f"Error loading form: {str(e)}")


@module.route("/save-gas-formulas/<form_id>", methods=["POST"])
@login_required
@permissions_required_all(["แก้ไขฟอร์ม"])
def save_gas_formulas(form_id):
    """บันทึกสูตรก๊าซ 7 ชนิด"""
    try:
        # ตรวจสอบว่า form_id เป็น ObjectId ที่ถูกต้องหรือไม่
        try:
            ObjectId(form_id)
        except InvalidId:
            return error_response("Form ID ไม่ถูกต้อง")
        
        form_obj = FormAndFormula.objects(id=ObjectId(form_id)).first()
        if not form_obj:
            return error_response("ไม่พบฟอร์มที่ต้องการ")
        
        # อัปเดตสูตรก๊าซทั้ง 7 ชนิด
        form_obj.formula_co2 = request.form.get("formula_co2", "")
        form_obj.formula_ch4 = request.form.get("formula_ch4", "")
        form_obj.formula_n2o = request.form.get("formula_n2o", "")
        form_obj.formula_hfcs = request.form.get("formula_hfcs", "")
        form_obj.formula_pfcs = request.form.get("formula_pfcs", "")
        form_obj.formula_sf6 = request.form.get("formula_sf6", "")
        form_obj.formula_nf3 = request.form.get("formula_nf3", "")
        form_obj.save()
        
        # อัปเดต Material ทั้งหมดที่ใช้ฟอร์มนี้
        _update_materials_with_gas_formulas(form_obj)
        
        return success_response(
            "บันทึกสูตรก๊าซสำเร็จ!",
            closeModal=True,
            refreshAllScopes={"scope": str(form_obj.ghg_scope)},
            refreshScopeContent={"scope": str(form_obj.ghg_scope)},
            updateActiveScopeCard={"scope": str(form_obj.ghg_scope)},
            **{f"refreshScope{form_obj.ghg_scope}": True}
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return error_response(f"เกิดข้อผิดพลาด: {str(e)}")


# === CALCULATOR ROUTES ===
@module.route("/calculator/show-conversion", methods=["POST"])
@login_required
def calculator_show_conversion():
    """แสดง calculator สำหรับสูตรแปลงหน่วย"""
    try:
        form_data = request.form.to_dict()
        variables = _get_calculator_variables(form_data, 'conversion')
        
        return render_template(
            "form-management/partials/unified-calculator.html",
            variables=variables,
            calculator_type="conversion"
        )
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/calculator/show-conversion2", methods=["POST"])
@login_required
def calculator_show_conversion2():
    """แสดง calculator สำหรับสูตรแปลงหน่วยที่ 2"""
    try:
        form_data = request.form.to_dict()
        variables = _get_calculator_variables(form_data, 'conversion2')
        
        return render_template(
            "form-management/partials/unified-calculator.html",
            variables=variables,
            calculator_type="conversion2"
        )
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/calculator/show-gas", methods=["POST"])
@login_required
def calculator_show_gas():
    """แสดง calculator สำหรับสูตรก๊าซ"""
    try:
        form_data = request.form.to_dict()
        gas_type = form_data.get('gas_type', 'co2')
        variables = _get_calculator_variables(form_data, gas_type)
        
        return render_template(
            "form-management/partials/unified-calculator.html",
            variables=variables,
            calculator_type="gas",
            gas_type=gas_type
        )
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/calculator/preview-conversion", methods=["POST"])
@login_required
def calculator_preview_conversion():
    """พรีวิวผลลัพธ์สูตรแปลงหน่วย"""
    try:
        formula = request.form.get('formula', '')
        if not formula:
            return '<div class="mt-3 p-3 bg-gray-50 rounded-lg hidden"></div>'
        
        # สร้างตัวอย่างค่าสำหรับการคำนวณ
        sample_values = _get_sample_values()
        result = _evaluate_formula(formula, sample_values)
        
        return render_template(
            "form-management/partials/formula-preview.html",
            result=result,
            formula_type="conversion"
        )
    except Exception as e:
        return f'<div class="mt-3 p-3 bg-red-50 rounded-lg"><p class="text-sm text-red-600">Error: {str(e)}</p></div>'


@module.route("/calculator/preview-conversion2", methods=["POST"])
@login_required
def calculator_preview_conversion2():
    """พรีวิวผลลัพธ์สูตรแปลงหน่วยที่ 2"""
    try:
        formula = request.form.get('formula2', '')
        if not formula:
            return '<div class="mt-3 p-3 bg-gray-50 rounded-lg hidden"></div>'
        
        # สร้างตัวอย่างค่าสำหรับการคำนวณ
        sample_values = _get_sample_values()
        sample_values['result'] = 100  # ตัวอย่างค่า result
        result = _evaluate_formula(formula, sample_values)
        
        return render_template(
            "form-management/partials/formula-preview.html",
            result=result,
            formula_type="conversion2"
        )
    except Exception as e:
        return f'<div class="mt-3 p-3 bg-red-50 rounded-lg"><p class="text-sm text-red-600">Error: {str(e)}</p></div>'


@module.route("/calculator/preview-gas", methods=["POST"])
@login_required
def calculator_preview_gas():
    """พรีวิวผลลัพธ์สูตรก๊าซ"""
    try:
        gas_type = request.form.get('gas_type', 'co2')
        formula_field = f'formula_{gas_type}'
        formula = request.form.get(formula_field, '')
        
        if not formula:
            return '<div class="mt-3 p-3 bg-gray-50 rounded-lg hidden"></div>'
        
        # สร้างตัวอย่างค่าสำหรับการคำนวณ
        sample_values = _get_sample_values()
        sample_values['result'] = 100  # ตัวอย่างค่า result
        result = _evaluate_formula(formula, sample_values)
        
        return render_template(
            "form-management/partials/formula-preview.html",
            result=result,
            formula_type=gas_type
        )
    except Exception as e:
        return f'<div class="mt-3 p-3 bg-red-50 rounded-lg"><p class="text-sm text-red-600">Error: {str(e)}</p></div>'


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




@module.route("/calculator/add-value-conversion", methods=["POST"])
@login_required
def calculator_add_value_conversion():
    """เพิ่มค่าลงในสูตรแปลงหน่วย"""
    try:
        calculator_type = request.form.get('calculator_type', 'conversion')
        new_value = request.form.get('value', '')
        
        # ดึงค่าปัจจุบันจาก form field ที่เกี่ยวข้อง
        if calculator_type == 'conversion2':
            current_formula = request.form.get('formula2', '')
            formula_field = 'formula2'
        else:
            current_formula = request.form.get('formula', '')
            formula_field = 'formula'
            
        updated_formula = current_formula + str(new_value)
        
        # ส่งคืน HTML template สำหรับ hx-swap="outerHTML"
        return render_template(
            "form-management/partials/unified-formula-input.html",
            input_type=calculator_type,
            formula_field=formula_field,
            conversion_type=calculator_type,
            formula_value=updated_formula
        )
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/calculator/add-value-conversion2", methods=["POST"])
@login_required
def calculator_add_value_conversion2():
    """เพิ่มค่าลงในสูตรแปลงหน่วยที่ 2"""
    try:
        calculator_type = request.form.get('calculator_type', 'conversion2')
        current_formula = request.form.get('formula2', '')
        new_value = request.form.get('value', '')
        updated_formula = current_formula + str(new_value)
        
        # ส่งคืน HTML สำหรับอัปเดตช่อง input โดยตรง
        return render_template(
            "form-management/partials/unified-formula-input.html",
            input_type=calculator_type,
            formula_field='formula2',
            conversion_type=calculator_type,
            formula_value=updated_formula
        )
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/calculator/remove-last-conversion", methods=["POST"])
@login_required
def calculator_remove_last_conversion():
    """ลบตัวอักษรสุดท้ายในสูตรแปลงหน่วย"""
    try:
        calculator_type = request.form.get('calculator_type', 'conversion')
        
        # ดึงค่าปัจจุบันจาก form field ที่เกี่ยวข้อง
        if calculator_type == 'conversion2':
            current_formula = request.form.get('formula2', '')
            formula_field = 'formula2'
        else:
            current_formula = request.form.get('formula', '')
            formula_field = 'formula'
            
        updated_formula = current_formula[:-1] if current_formula else ''
        
        # ส่งคืน HTML template สำหรับ hx-swap="outerHTML"
        return render_template(
            "form-management/partials/unified-formula-input.html",
            input_type=calculator_type,
            formula_field=formula_field,
            conversion_type=calculator_type,
            formula_value=updated_formula
        )
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/calculator/clear-conversion", methods=["POST"])
@login_required
def calculator_clear_conversion():
    """ล้างสูตรแปลงหน่วยทั้งหมด"""
    try:
        calculator_type = request.form.get('calculator_type', 'conversion')
        formula_field = 'formula2' if calculator_type == 'conversion2' else 'formula'
        
        # ส่งคืน HTML template สำหรับ hx-swap="outerHTML"
        return render_template(
            "form-management/partials/unified-formula-input.html",
            input_type=calculator_type,
            formula_field=formula_field,
            conversion_type=calculator_type,
            formula_value=""
        )
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/calculator/remove-last-conversion2", methods=["POST"])
@login_required
def calculator_remove_last_conversion2():
    """ลบตัวอักษรสุดท้ายในสูตรแปลงหน่วยที่ 2"""
    try:
        calculator_type = request.form.get('calculator_type', 'conversion2')
        current_formula = request.form.get('formula2', '')
        updated_formula = current_formula[:-1] if current_formula else ''
        
        # ส่งคืน HTML สำหรับอัปเดตช่อง input โดยตรง
        return render_template(
            "form-management/partials/unified-formula-input.html",
            input_type=calculator_type,
            formula_field='formula2',
            conversion_type=calculator_type,
            formula_value=updated_formula
        )
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/calculator/clear-conversion2", methods=["POST"])
@login_required
def calculator_clear_conversion2():
    """ล้างสูตรแปลงหน่วยที่ 2 ทั้งหมด"""
    try:
        calculator_type = request.form.get('calculator_type', 'conversion2')
        
        # ส่งคืน HTML สำหรับอัปเดตช่อง input โดยตรง
        return render_template(
            "form-management/partials/unified-formula-input.html",
            input_type=calculator_type,
            formula_field='formula2',
            conversion_type=calculator_type,
            formula_value=""
        )
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/calculator/hide-conversion", methods=["POST"])
@login_required
def calculator_hide_conversion():
    """ปิด calculator สำหรับสูตรแปลงหน่วย"""
    return ""


@module.route("/calculator/hide-conversion2", methods=["POST"])
@login_required
def calculator_hide_conversion2():
    """ปิด calculator สำหรับสูตรแปลงหน่วยที่ 2"""
    return ""


@module.route("/calculator/hide-gas", methods=["POST"])
@login_required
def calculator_hide_gas():
    """ปิด calculator สำหรับสูตรก๊าซ"""
    return ""


@module.route("/calculator/add-value-gas", methods=["POST"])
@login_required
def calculator_add_value_gas():
    """เพิ่มค่าลงในสูตรก๊าซ"""
    try:
        gas_type = request.form.get('gas_type', 'co2')
        target_field = f'formula_{gas_type}'
        current_formula = request.form.get(target_field, '')
        new_value = request.form.get('value', '')
        updated_formula = current_formula + str(new_value)
        
        # ส่งคืน HTML template สำหรับ hx-swap="outerHTML"
        return render_template(
            "form-management/partials/unified-formula-input.html",
            input_type="gas",
            formula_field=target_field,
            gas_type=gas_type,
            formula_value=updated_formula
        )
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/calculator/remove-last-gas", methods=["POST"])
@login_required
def calculator_remove_last_gas():
    """ลบตัวอักษรสุดท้ายในสูตรก๊าซ"""
    try:
        gas_type = request.form.get('gas_type', 'co2')
        target_field = f'formula_{gas_type}'
        current_formula = request.form.get(target_field, '')
        updated_formula = current_formula[:-1] if current_formula else ''
        
        # ส่งคืน HTML template สำหรับ hx-swap="outerHTML"
        return render_template(
            "form-management/partials/unified-formula-input.html",
            input_type="gas",
            formula_field=target_field,
            gas_type=gas_type,
            formula_value=updated_formula
        )
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


@module.route("/calculator/clear-gas", methods=["POST"])
@login_required
def calculator_clear_gas():
    """ล้างสูตรก๊าซทั้งหมด"""
    try:
        gas_type = request.form.get('gas_type', 'co2')
        target_field = f'formula_{gas_type}'
        
        # ส่งคืน HTML template สำหรับ hx-swap="outerHTML"
        return render_template(
            "form-management/partials/unified-formula-input.html",
            input_type="gas",
            formula_field=target_field,
            gas_type=gas_type,
            formula_value=""
        )
    except Exception as e:
        return f'<div class="text-error">Error: {str(e)}</div>'


# === HELPER FUNCTIONS ===
def _get_calculator_variables(form_data, calculator_type=None):
    """ดึง variables สำหรับ calculator"""
    variables = []
    
    # ดึงข้อมูล form จาก form_id หรือ material_name
    form_id = form_data.get('form_id')
    material_name = form_data.get('material_name')
    
    if form_id:
        try:
            form_obj = FormAndFormula.objects(id=ObjectId(form_id)).first()
            if form_obj:
                # ดึงตัวแปรจาก input_types ถ้ามี
                if form_obj.input_types:
                    for input_type in form_obj.input_types:
                        variables.append({
                            'field': input_type.field,
                            'label': input_type.label,
                            'color': 'bg-green-100 text-green-800'
                        })
                # ถ้าไม่มี input_types ให้ใช้ variables เก่า
                elif form_obj.variables:
                    for var in form_obj.variables:
                        variables.append({
                            'field': var,
                            'label': var,
                            'color': 'bg-green-100 text-green-800'
                        })
        except:
            pass
    elif material_name:
        form_obj = FormAndFormula.objects(material_name=material_name).first()
        if form_obj:
            # ดึงตัวแปรจาก input_types ถ้ามี
            if form_obj.input_types:
                for input_type in form_obj.input_types:
                    variables.append({
                        'field': input_type.field,
                        'label': input_type.label,
                        'color': 'bg-green-100 text-green-800'
                    })
            # ถ้าไม่มี input_types ให้ใช้ variables เก่า
            elif form_obj.variables:
                for var in form_obj.variables:
                    variables.append({
                        'field': var,
                        'label': var,
                        'color': 'bg-green-100 text-green-800'
                    })
    
    # เพิ่มตัวแปรพื้นฐานตามประเภท calculator
    if calculator_type:
        if calculator_type in ['conversion', 'conversion2']:
            # สูตรแปลงหน่วย - ไม่ต้องมี result/result2
            pass
        elif calculator_type == 'carbon':
            # สูตรคำนวณคาร์บอน - ต้องมี result
            variables.append({
                'field': 'result',
                'label': 'ผลลัพธ์หลัก',
                'color': 'bg-blue-100 text-blue-800'
            })
        elif calculator_type in ['co2', 'ch4', 'n2o', 'hfcs', 'pfcs', 'sf6', 'nf3']:
            # สูตรคำนวณก๊าซ - ต้องมี result และ result2
            variables.extend([
                {'field': 'result', 'label': 'ผลลัพธ์หลัก', 'color': 'bg-blue-100 text-blue-800'},
                {'field': 'result2', 'label': 'ผลลัพธ์ที่ 2', 'color': 'bg-purple-100 text-purple-800'}
            ])
    else:
        # กรณีไม่ระบุประเภท (default)
        variables.extend([
            {'field': 'result', 'label': 'ผลลัพธ์หลัก', 'color': 'bg-blue-100 text-blue-800'},
            {'field': 'result2', 'label': 'ผลลัพธ์ที่ 2', 'color': 'bg-purple-100 text-purple-800'}
        ])
    
    return variables


def _get_sample_values():
    """สร้างค่าตัวอย่างสำหรับการคำนวณ"""
    return {
        'diesel': 100,
        'gasoline': 50,
        'electricity': 1000,
        'water': 500,
        'waste': 200,
        'result': 100,
        'result2': 0.1
    }


def _evaluate_formula(formula, variables):
    """ประเมินสูตรด้วยค่าตัวแปรที่กำหนด"""
    try:
        # แทนที่ตัวแปรในสูตร
        formula_to_execute = formula
        for var_name, value in variables.items():
            formula_to_execute = formula_to_execute.replace(var_name, str(value))
        
        # คำนวณผลลัพธ์
        result = eval(formula_to_execute)
        return float(result)
    except:
        return None


def _update_materials_with_new_formulas(form_obj):
    """อัปเดต Material ทั้งหมดเมื่อมีการเปลี่ยนสูตรแปลงหน่วย"""
    try:
        from ..views.emissoins import calculate_result
        
        materials = Material.objects(
            name=form_obj.material_name,
            scope=form_obj.ghg_scope,
            sub_scope=form_obj.ghg_sup_scope
        )
        
        for material in materials:
            try:
                calculate_result(material)
            except Exception as e:
                print(f"Error updating material {material.id}: {e}")
                continue
                
    except Exception as e:
        print(f"Error in _update_materials_with_new_formulas: {e}")


def _update_materials_with_gas_formulas(form_obj):
    """อัปเดต Material ทั้งหมดเมื่อมีการเปลี่ยนสูตรก๊าซ"""
    try:
        from ..views.emissoins import calculate_result
        
        materials = Material.objects(
            name=form_obj.material_name,
            scope=form_obj.ghg_scope,
            sub_scope=form_obj.ghg_sup_scope
        )
        
        for material in materials:
            try:
                # ใช้ calculate_result จาก emissoins.py ซึ่งรวมการคำนวณก๊าซแล้ว
                calculate_result(material)
            except Exception as e:
                print(f"Error updating gas results for material {material.id}: {e}")
                continue
                
    except Exception as e:
        print(f"Error in _update_materials_with_gas_formulas: {e}")


# === REFRESH GAS CALCULATIONS ROUTE ===
@module.route("/refresh-gas-calculations/<form_id>", methods=["POST"])
@login_required
@permissions_required_all(["แก้ไขฟอร์ม"])
def refresh_gas_calculations(form_id):
    """รีเฟรชคำนวณก๊าซทั้งหมดสำหรับฟอร์มนี้"""
    try:
        form_obj = FormAndFormula.objects(id=ObjectId(form_id)).first()
        if not form_obj:
            return error_response("ไม่พบฟอร์มที่ต้องการ")
        
        # อัปเดต Material ทั้งหมดที่ใช้ฟอร์มนี้
        from ..views.emissoins import calculate_result
        
        materials = Material.objects(
            name=form_obj.material_name,
            scope=form_obj.ghg_scope,
            sub_scope=form_obj.ghg_sup_scope
        )
        
        updated_count = 0
        for material in materials:
            try:
                calculate_result(material)
                updated_count += 1
            except Exception as e:
                print(f"Error recalculating for material {material.id}: {e}")
                continue
        
        return success_response(
            f"รีเฟรชคำนวณก๊าซสำเร็จ! อัปเดต {updated_count} รายการ",
            closeModal=True,
            refreshAllScopes={"scope": str(form_obj.ghg_scope)},
            refreshScopeContent={"scope": str(form_obj.ghg_scope)},
            updateActiveScopeCard={"scope": str(form_obj.ghg_scope)},
            **{f"refreshScope{form_obj.ghg_scope}": True}
        )
        
    except Exception as e:
        return error_response(f"เกิดข้อผิดพลาด: {str(e)}")
