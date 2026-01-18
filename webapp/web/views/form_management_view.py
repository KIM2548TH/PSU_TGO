"""
Form Management - จัดการฟอร์ม CRUD
Display, Add, Edit, Delete, Update Materials
"""
from flask import Blueprint, render_template, request, jsonify, make_response
from flask_login import login_required, current_user
from ...models import FormAndFormula, Scope, Material, InputType
from ...models.materail_model import QuantityType
from ..views.emissoins import calculate_result
from ..utils.acl import permissions_required_all
from ..utils.toast_utils import success_response, error_response
from bson import ObjectId
from bson.errors import InvalidId
import datetime

module = Blueprint("form_management", __name__, url_prefix="/form-management")

# Register form builder as sub-blueprint
from . import form_management_builder
module.register_blueprint(form_management_builder.module)


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


@module.route("/refresh-forms", methods=["GET"])
@login_required
def refresh_forms():
    """รีเฟรชข้อมูลฟอร์ม (สำหรับ partial update)"""
    try:
        # รับค่า scope ที่ต้องการรีเฟรช
        scope_id = request.args.get('scope', '1')  # default เป็น scope 1
        filter_sub_scope = request.args.get('filter_sub_scope')
        show_all = request.args.get('show_all', 'false').lower() == 'true'
        
        # ไม่ต้อง fallback จาก referer หรือ event.detail.scope
        # scope_id จะถูกส่งมาจาก hx-vals โดยตรง
        print(f"refresh_forms: scope_id={scope_id}")

        forms = FormAndFormula.objects().order_by(
            "ghg_scope", "ghg_sup_scope", "material_name"
        )

        # ดึงข้อมูล scope names จาก Scope model
        scopes = Scope.objects().order_by("ghg_scope", "ghg_sup_scope")
        scope_names = {}

        for scope in scopes:
            key = f"{scope.ghg_scope}.{scope.ghg_sup_scope}"
            scope_names[key] = scope.ghg_name

        # เลือก template ตาม scope
        template_map = {
            '1': "form-management/partials/scope1-content.html",
            '2': "form-management/partials/scope2-content.html",  
            '3': "form-management/partials/scope3-content.html"
        }
        
        template_name = template_map.get(str(scope_id), template_map['1'])
        
        return render_template(
            template_name,
            forms=forms,
            scope_names=scope_names,
            active_scope=scope_id,
            filter_sub_scope=int(filter_sub_scope) if filter_sub_scope else None,
            show_all=show_all
        )
    except Exception as e:
        return f'<div class="alert alert-error">Error refreshing forms: {str(e)}</div>'


# === FORM LOADING ROUTES ===
@module.route("/load-add-form", methods=["GET"])
@login_required
def load_add_form_and_formula():
    """โหลดหน้าเพิ่มฟอร์มใหม่ พร้อม default values"""
    try:
        # รับค่า default จาก query parameters
        default_scope = request.args.get("default_scope")
        default_sub_scope = request.args.get("default_sub_scope")
        
        # แปลงเป็น int ถ้ามีค่า
        if default_scope:
            try:
                default_scope = int(default_scope)
            except ValueError:
                default_scope = None
                
        if default_sub_scope:
            try:
                default_sub_scope = int(default_sub_scope)
            except ValueError:
                default_sub_scope = None
        
        return render_template(
            "/form-management/add-form-and-formula.html",
            default_scope=default_scope,
            default_sub_scope=default_sub_scope,
        )
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in load_add_form_and_formula: {str(e)}")
        print(f"Full traceback: {error_details}")
        
        # ส่งกลับหน้า error แทน
        return render_template(
            "/form-management/add-form-and-formula.html",
            default_scope=None,
            default_sub_scope=None,
            error_msg=f"Error loading form: {str(e)}"
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
@module.route("/scope1", methods=["GET"])
@login_required
def get_scope1_content():
    """โหลด content สำหรับ scope 1"""
    return _get_scope_content(1)

@module.route("/scope2", methods=["GET"])
@login_required
def get_scope2_content():
    """โหลด content สำหรับ scope 2"""
    return _get_scope_content(2)

@module.route("/scope3", methods=["GET"])
@login_required
def get_scope3_content():
    """โหลด content สำหรับ scope 3"""
    return _get_scope_content(3)

@module.route("/scope/<int:scope_id>", methods=["GET"])
@login_required
def get_scope_content(scope_id):
    """โหลด content ตาม scope ที่เลือก (เก็บไว้เพื่อความเข้ากันได้แบบย้อนหลัง)"""
    return _get_scope_content(scope_id)


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
        formula2 = request.form.get("formula2", "")
        ghg_scope = request.form.get("scope")
        ghg_sup_scope = request.form.get("sup_scope")

        # เพิ่มการจัดการลิงก์
        form_type = request.form.get("form_type", "normal")
        is_linked = form_type == "linked"
        
        # รองรับการเลือกหลายฟอร์ม (รับเป็น JSON array)
        linked_forms_raw = request.form.get("linked_forms", "")
        linked_forms = []
        if linked_forms_raw:
            try:
                import json
                linked_forms = json.loads(linked_forms_raw)
            except:
                # ถ้าไม่ใช่ JSON ลองแยกด้วย comma
                linked_forms = [f.strip() for f in linked_forms_raw.split(",") if f.strip()]

        # ตรวจสอบข้อมูลที่จำเป็น (formula ไม่จำเป็นต้องกรอก)
        if not material_name or not ghg_scope or not ghg_sup_scope:
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
            linked_forms=linked_forms if is_linked else [],
        )

        if is_linked and linked_forms:
            _setup_linked_form_fields(new_form, linked_forms)
        else:
            _setup_normal_form_fields(new_form)
        
        new_form.save()
        
        # อัปเดต used_by_forms ของ source forms ทันที
        if is_linked and linked_forms:
            _update_used_by_forms(new_form.id, linked_forms)
        
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

        # อัปเดต input fields
        form_type = request.form.get("form_type", "normal")
        is_linked = form_type == "linked"
        
        # อัปเดต is_linked status
        form.is_linked = is_linked
        
        # เก็บ linked_forms เก่าไว้เพื่อเอาออกจาก used_by_forms
        old_linked_forms = list(form.linked_forms) if form.linked_forms else []
        
        if is_linked:
            # ดึง linked_forms จาก request ไม่ใช่จาก database เก่า
            linked_forms_raw = request.form.get("linked_forms", "")
            print(f"🔍 DEBUG: linked_forms_raw from request = {linked_forms_raw}")
            
            linked_forms = []
            if linked_forms_raw:
                try:
                    import json
                    linked_forms = json.loads(linked_forms_raw)
                    print(f"🔍 DEBUG: Parsed linked_forms = {linked_forms}")
                except Exception as e:
                    print(f"🔍 DEBUG: JSON parse failed, trying split: {e}")
                    linked_forms = [f.strip() for f in linked_forms_raw.split(",") if f.strip()]
            
            print(f"🔍 DEBUG: old_linked_forms = {old_linked_forms}")
            print(f"🔍 DEBUG: new linked_forms = {linked_forms}")
            
            form.linked_forms = linked_forms
            if linked_forms:
                _setup_linked_form_fields(form, linked_forms)
        else:
            form.linked_forms = []
            _setup_normal_form_fields(form)

        form.save()
        
        # อัปเดต used_by_forms ของ source forms
        # 1. ลบฟอร์มนี้ออกจาก used_by_forms ของฟอร์มเก่าที่ไม่ได้ใช้แล้ว
        print(f"🔍 DEBUG: Removing form {form.id} from old_linked_forms: {old_linked_forms}")
        _remove_from_used_by_forms(form.id, old_linked_forms)
        
        # 2. เพิ่มฟอร์มนี้เข้า used_by_forms ของฟอร์มใหม่
        if is_linked and form.linked_forms:
            print(f"🔍 DEBUG: Adding form {form.id} to new linked_forms: {form.linked_forms}")
            _update_used_by_forms(form.id, form.linked_forms)
        
        return _success_response("บันทึกการแก้ไขสำเร็จ!", form.ghg_scope)

    except Exception as e:
        return _error_response(f"Failed to update form: {str(e)}")


@module.route("/delete-form/<form_id>", methods=["DELETE"])
@login_required
@permissions_required_all(["ลบฟอร์ม"])
def delete_form(form_id):
    """ลบฟอร์ม"""
    try:
        
        form = FormAndFormula.objects(id=ObjectId(form_id)).first()
        if not form:
            return _error_response("Form not found")
        
        form_name = form.material_name
        scope = form.ghg_scope
        
        # ลบฟอร์มนี้ออกจาก used_by_forms ของ source forms ที่ link มา
        if form.linked_forms:
            _remove_from_used_by_forms(form.id, form.linked_forms)
        
        form.delete()
        
        return _success_response(f"ลบฟอร์ม '{form_name}' สำเร็จ!", scope)
        
    except Exception as e:
        return _error_response(f"Error deleting form: {str(e)}")


@module.route("/update-materials/<form_id>", methods=["POST"])
@login_required
@permissions_required_all(["แก้ไขฟอร์ม"])
def update_materials(form_id):
    """อัปเดต Material ทั้งหมดที่ใช้ฟอร์มนี้และคำนวณผลลัพธ์ใหม่"""
    try:
        # ดึงข้อมูลฟอร์ม
        form = FormAndFormula.objects(id=ObjectId(form_id)).first()
        if not form:
            return _error_response("ไม่พบฟอร์มที่ต้องการ")

        # ค้นหา Material ทั้งหมดที่ใช้ฟอร์มนี้
        materials = Material.objects(
            name=form.material_name,
            scope=form.ghg_scope,
            sub_scope=form.ghg_sup_scope
        )

        updated_count = 0
        for material in materials:
            try:
                # คำนวณผลลัพธ์ใหม่
                calculate_result(material)
                updated_count += 1
            except Exception as e:
                print(f"Error updating material : {e}")
                continue

        # ตรวจสอบว่ามี linked forms หรือไม่ (forms ที่ลิงก์มายังฟอร์มนี้)
        linked_updated_count = 0
        linked_created_count = 0
        
        # ค้นหาฟอร์มที่มี form ID นี้อยู่ใน linked_forms array
        linked_forms = FormAndFormula.objects(
            linked_forms=str(form.id),
            is_linked=True
        )
        
        if linked_forms:
            # ดึงรายการเดือน/ปี/แผนก/วิทยาเขตที่มี Material ต้นฉบับ
            source_materials_info = set()
            for material in materials:
                source_materials_info.add((
                    material.month,
                    material.year, 
                    material.department,
                    material.campus
                ))
            
            for linked_form in linked_forms:
                for month, year, department, campus in source_materials_info:
                    # ตรวจสอบว่ามี linked material ในเดือน/ปี/แผนก/วิทยาเขตนี้หรือไม่
                    existing_linked_material = Material.objects(
                        name=linked_form.material_name,
                        scope=linked_form.ghg_scope,
                        sub_scope=linked_form.ghg_sup_scope,
                        month=month,
                        year=year,
                        department=department,
                        campus=campus
                    ).first()
                    
                    # ดึงข้อมูล source material ในเดือนนี้
                    source_material = Material.objects(
                        name=form.material_name,
                        scope=form.ghg_scope,
                        sub_scope=form.ghg_sup_scope,
                        month=month,
                        year=year,
                        department=department,
                        campus=campus
                    ).first()
                    
                    if not source_material:
                        continue
                        
                    # สร้าง quantity_type สำหรับ linked material
                    linked_quantity_types = []
                    if source_material.result is not None and linked_form.input_types:
                        first_input = linked_form.input_types[0]
                        linked_quantity_types = [
                            QuantityType(
                                field=first_input.field,
                                label=first_input.label,
                                amount=float(source_material.result),
                                unit=first_input.unit,
                            )
                        ]
                    
                    if existing_linked_material:
                        # อัปเดต Material ที่มีอยู่
                        try:
                            existing_linked_material.quantity_type = linked_quantity_types
                            existing_linked_material.is_linked = True
                            existing_linked_material.edit_by_id = str(current_user.id)
                            existing_linked_material.update_date = datetime.datetime.now()
                            existing_linked_material.save()
                            
                            # คำนวณ result ใหม่
                            calculate_result(existing_linked_material)
                            linked_updated_count += 1
                        except Exception as e:
                            print(f"Error updating existing linked material: {e}")
                            continue
                    else:
                        # สร้าง Material ใหม่
                        try:
                            new_linked_material = Material(
                                month=month,
                                name=linked_form.material_name,
                                scope=linked_form.ghg_scope,
                                sub_scope=linked_form.ghg_sup_scope,
                                year=year,
                                day=1,
                                form_and_formula=str(linked_form.id),
                                department=department,
                                campus=campus,
                                edit_by_id=str(current_user.id),
                                update_date=datetime.datetime.now(),
                                quantity_type=linked_quantity_types,
                                is_linked=True,
                            )
                            new_linked_material.save()
                            
                            # คำนวณ result ตามสูตรของ linked material
                            calculate_result(new_linked_material)
                            linked_created_count += 1
                        except Exception as e:
                            print(f"Error creating new linked material: {e}")
                            continue

        # สร้างข้อความแสดงผล
        total_updated = updated_count + linked_updated_count
        message = f"อัปเดต Material สำเร็จ! ({updated_count} รายการหลัก"
        
        if linked_updated_count > 0:
            message += f", {linked_updated_count} รายการที่เชื่อมโยงอัปเดต"
        if linked_created_count > 0:
            message += f", {linked_created_count} รายการที่เชื่อมโยงสร้างใหม่"
        message += ")"

        return _success_response(message, form.ghg_scope)

    except Exception as e:
        return _error_response(f"เกิดข้อผิดพลาดในการอัปเดต: {str(e)}")


# === HELPER FUNCTIONS ===

def _success_response(message, refresh_scope=None):
    """สร้าง success response พร้อม toast notification"""
    trigger_data = {"closeModal": True}
    if refresh_scope:
        trigger_data["refreshAllScopes"] = {"scope": str(refresh_scope)}
        trigger_data["refreshScopeContent"] = {"scope": str(refresh_scope)}
        trigger_data["updateActiveScopeCard"] = {"scope": str(refresh_scope)}
        trigger_data[f"refreshScope{refresh_scope}"] = True
        return success_response(message, **trigger_data)
    else:
        return success_response(message, **trigger_data)


def _error_response(message):
    """สร้าง error response พร้อม toast notification"""
    return error_response(message, content=f'<div class="alert alert-error"><span>{message}</span></div>', HX_Retarget='#modal-content')


def _get_scope_content(scope_id):
    """Helper function สำหรับโหลด content ตาม scope"""
    try:
        forms = FormAndFormula.objects().order_by(
            "ghg_scope", "ghg_sup_scope", "material_name"
        )
        
        scopes = Scope.objects().order_by("ghg_scope", "ghg_sup_scope")
        scope_names = {}
        for scope in scopes:
            key = f"{scope.ghg_scope}.{scope.ghg_sup_scope}"
            scope_names[key] = scope.ghg_name
        
        filter_sub_scope = request.args.get('filter_sub_scope')
        show_all = request.args.get('show_all', 'false').lower() == 'true'
        
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


def _convert_form_to_dict(form_obj):
    """แปลง FormAndFormula object เป็น dict พร้อม linked form names"""
    # Query linked forms เพื่อเอา names - ใช้ list comprehension แทน loop
    linked_forms_data = []
    if getattr(form_obj, "linked_forms", []):
        try:
            # Query ทีเดียวแทนการ query ใน loop
            from bson import ObjectId
            form_ids = [ObjectId(fid) for fid in form_obj.linked_forms if fid]
            linked_forms_objs = FormAndFormula.objects(id__in=form_ids).only('id', 'material_name')
            
            # สร้าง dict mapping
            forms_map = {str(f.id): f.material_name for f in linked_forms_objs}
            
            # เรียงตาม order ของ linked_forms
            linked_forms_data = [
                {"id": fid, "name": forms_map.get(fid, "Unknown")}
                for fid in form_obj.linked_forms
            ]
        except Exception as e:
            print(f"Error querying linked forms: {e}")
    
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
        "linked_forms": getattr(form_obj, "linked_forms", []),
        "linked_forms_data": linked_forms_data,  # เพิ่ม form names
        "input_types": [
            {
                "field": input_field.field,
                "label": input_field.label,
                "input_type": input_field.input_type,
                "unit": input_field.unit,
                "source_form_id": getattr(input_field, "source_form_id", None),
                "is_used": getattr(input_field, "is_used", True),
            }
            for input_field in form_obj.input_types or []
        ]
    }


def _setup_linked_form_fields(form_obj, linked_form_ids):
    """ตั้งค่า input fields สำหรับ linked form - ลอก InputType ต้นฉบับมาเลย"""
    if not linked_form_ids:
        return
        
    # รองรับทั้ง string เดียวและ list
    if isinstance(linked_form_ids, str):
        linked_form_ids = [linked_form_ids]
    
    input_fields = []
    variables = []
    
    # 1. เพิ่มฟิลด์จาก linked forms
    # ดึงข้อมูลว่าฟิลด์ไหนถูกเลือกใช้ (format: "field_formid")
    linked_fields_used_raw = request.form.getlist('linked_field_used')
    print(f"🔍 DEBUG: linked_fields_used_raw = {linked_fields_used_raw}")
    print(f"🔍 DEBUG: linked_form_ids = {linked_form_ids}")
    
    for form_id in linked_form_ids:
        # ค้นหาฟอร์มจาก ID
        from bson import ObjectId
        try:
            linked_form = FormAndFormula.objects(id=ObjectId(form_id)).first()
        except Exception as e:
            print(f"🔍 DEBUG: Error loading form {form_id}: {e}")
            continue
        
        if not linked_form:
            print(f"🔍 DEBUG: Form {form_id} not found")
            continue
            
        if not linked_form.input_types:
            print(f"🔍 DEBUG: Form {form_id} ({linked_form.material_name}) has no input_types")
            continue
        
        print(f"🔍 DEBUG: Processing form {form_id} ({linked_form.material_name}) with {len(linked_form.input_types)} input_types")
        
        # ดึงชื่อฟอร์มต้นฉบับ
        material_name = linked_form.material_name
        
        for quantity in linked_form.input_types:
            # ตรวจสอบว่า quantity นี้มี source_form_id หรือไม่ (อาจเป็น custom field)
            if hasattr(quantity, 'source_form_id') and quantity.source_form_id:
                print(f"🔍 DEBUG: Skipping field {quantity.field} from form {form_id} - it has source_form_id (already a linked field)")
                continue
            
            # ใช้ original field สำหรับสร้าง identifier เพื่อเช็คกับ checkbox
            # เพราะ quantity.field อาจมีชื่อฟอร์มต่อท้ายแล้ว แต่ checkbox ส่งมาเป็น original_field
            original_field = quantity.field
            
            # สร้าง field identifier สำหรับเช็คว่าถูกเลือกหรือไม่ (ใช้ original field)
            field_identifier = f"{original_field}_{str(linked_form.id)}"
            field_with_source = f"{original_field}_{material_name}"
            
            # บันทึกตาม checkbox จาก UI
            is_used = field_identifier in linked_fields_used_raw
            
            print(f"🔍 DEBUG: original_field={original_field}, form_id={linked_form.id}")
            print(f"🔍 DEBUG: field_identifier={field_identifier}")
            print(f"🔍 DEBUG: is_used={is_used} (checked: {field_identifier in linked_fields_used_raw})")
            
            # สร้าง field name และ label ใหม่ ต่อท้ายด้วยชื่อฟอร์ม (ใช้รูปแบบเดียวกัน)
            label_with_source = f"{quantity.label}_{material_name}"
            
            # ลอก InputType แต่ต่อท้ายชื่อฟอร์ม และเก็บชื่อต้นฉบับไว้ใน original_field
            new_field = InputType.create_input(
                field=field_with_source,  # "ปริมาณ_ดีเซล"
                label=label_with_source,  # "ปริมาณ_ดีเซล"
                input_type=quantity.input_type,
                unit=quantity.unit,
                source_form_id=str(linked_form.id),  # บันทึก ID ต้นฉบับ
                is_used=is_used,
                original_field=original_field  # ชื่อต้นฉบับ: "ปริมาณ" (สำหรับดึงข้อมูล)
            )
            input_fields.append(new_field)
            
            # เพิ่มเข้า variables ถ้าถูกเลือกใช้
            if is_used:
                variables.append(field_with_source)  # ใช้ชื่อที่ต่อท้ายแล้ว
    
    # 2. เพิ่มฟิลด์ของตัวเอง (custom fields)
    custom_fields = request.form.getlist("custom_field")
    custom_labels = request.form.getlist("custom_label")
    custom_input_types = request.form.getlist("custom_input_type")
    custom_units = request.form.getlist("custom_unit")

    for i in range(len(custom_fields)):
        field = custom_fields[i]
        label = custom_labels[i] if i < len(custom_labels) else ""
        input_type = custom_input_types[i] if i < len(custom_input_types) else "text"
        unit = custom_units[i] if i < len(custom_units) else ""

        if field and input_type:
            # ฟิลด์ของตัวเอง: source_form_id = None
            custom_field = InputType.create_input(
                field=field,
                label=label,
                input_type=input_type,
                unit=unit,
                source_form_id=None,  # None = ฟิลด์ของตัวเอง
                is_used=True
            )
            input_fields.append(custom_field)
            variables.append(field)
    
    form_obj.input_types = input_fields
    form_obj.variables = variables


def _update_used_by_forms(linked_form_id, source_form_ids):
    """
    อัปเดต used_by_forms ของ source forms
    เพิ่ม linked_form_id เข้าไปใน used_by_forms ของแต่ละ source form
    """
    if not source_form_ids:
        return
        
    from bson import ObjectId
    linked_form_id_str = str(linked_form_id)
    
    for source_form_id in source_form_ids:
        try:
            source_form = FormAndFormula.objects(id=ObjectId(source_form_id)).first()
            if source_form:
                # เช็คว่ามี ID นี้อยู่แล้วหรือไม่
                if linked_form_id_str not in source_form.used_by_forms:
                    source_form.used_by_forms.append(linked_form_id_str)
                    source_form.save()
        except Exception as e:
            print(f"Error updating used_by_forms for {source_form_id}: {e}")
            continue


def _remove_from_used_by_forms(linked_form_id, source_form_ids):
    """
    ลบ linked_form_id ออกจาก used_by_forms ของ source forms
    ใช้เมื่อแก้ไขฟอร์มและเปลี่ยน linked_forms
    """
    if not source_form_ids:
        return
        
    from bson import ObjectId
    linked_form_id_str = str(linked_form_id)
    
    for source_form_id in source_form_ids:
        try:
            source_form = FormAndFormula.objects(id=ObjectId(source_form_id)).first()
            if source_form and linked_form_id_str in source_form.used_by_forms:
                source_form.used_by_forms.remove(linked_form_id_str)
                source_form.save()
        except Exception as e:
            print(f"Error removing from used_by_forms for {source_form_id}: {e}")
            continue


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


# === SUB SCOPE & UTILITY ROUTES ===
@module.route("/get-sub-scopes/<int:main_scope>", methods=["GET"])
@login_required
def get_sub_scopes(main_scope):
    """ดึง sub scopes ตาม main scope ที่เลือก และ render template"""
    try:
        # รับค่า main_scope จาก URL parameter
        if not main_scope:
            return '<select name="sup_scope" class="select select-bordered w-full mt-1" required><option value="">กรุณาเลือก Main Scope ก่อน</option></select>'
            
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


# === GAS FORMULAS ROUTE ===
@module.route("/gas-formulas/<form_id>", methods=["GET"])
@login_required
def get_gas_formulas(form_id):
    """ดึงข้อมูลสูตรคำนวณก๊าซสำหรับฟอร์มที่เลือก"""
    try:
        try:
            object_id = ObjectId(form_id)
        except InvalidId:
            return '<div class="text-center py-2 text-gray-500"><i data-feather="info" class="w-3 h-3 inline mr-1"></i>Invalid form ID</div>'
        
        form = FormAndFormula.objects(id=object_id).first()
        if not form:
            return '<div class="text-center py-2 text-gray-500"><i data-feather="info" class="w-3 h-3 inline mr-1"></i>Form not found</div>'

        # สร้างข้อมูล gas formulas
        gas_formulas = [
            {'name': 'สูตรคำนวณ CO₂', 'formula': form.formula_co2},
            {'name': 'สูตรคำนวณ CH₄', 'formula': form.formula_ch4},
            {'name': 'สูตรคำนวณ N₂O', 'formula': form.formula_n2o},
            {'name': 'สูตรคำนวณ HFCs', 'formula': form.formula_hfcs},
            {'name': 'สูตรคำนวณ PFCs', 'formula': form.formula_pfcs},
            {'name': 'สูตรคำนวณ SF₆', 'formula': form.formula_sf6},
            {'name': 'สูตรคำนวณ NF₃', 'formula': form.formula_nf3}
        ]
        
        # ตรวจสอบว่ามีสูตรหรือไม่
        has_formulas = any(gas['formula'] for gas in gas_formulas)
        
        if not has_formulas:
            # ถ้าไม่มีสูตร ให้แสดงข้อความแจ้งเตือน
            return '<div class="text-center py-2 text-gray-500"><i data-feather="info" class="w-3 h-3 inline mr-1"></i>ยังไม่มีข้อมูลสูตรคำนวณก๊าซ</div>'
        
        # สร้าง HTML สำหรับ gas formulas - ใช้สีธีมเดิมและไม่แสดง GWP
        html_content = '<div class="absolute z-50 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg p-2 max-h-32 overflow-y-auto">'
        
        for gas in gas_formulas:
            if gas['formula']:
                html_content += f'''
                <div class="py-1 px-2 hover:bg-gray-50 rounded border-b border-gray-100 last:border-b-0">
                    <div class="flex items-center gap-2">
                        <h4 class="text-xs font-medium text-gray-700">{gas['name']}</h4>
                    </div>
                    <div class="text-xs text-gray-600 mt-1">
                        <p class="font-mono break-all">{gas['formula']}</p>
                    </div>
                </div>
                '''
        
        html_content += '</div>'
        return html_content
        
    except Exception as e:
        return f'<div class="text-center py-2 text-red-500"><i data-feather="alert-circle" class="w-3 h-3 inline mr-1"></i>Error: {str(e)}</div>'


