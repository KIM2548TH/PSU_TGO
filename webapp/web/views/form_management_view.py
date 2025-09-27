from flask import Blueprint, render_template, redirect, url_for, request, jsonify,flash
from flask_login import login_required, logout_user, current_user
from ..forms.user_form import LoginForm, RegisterForm, EditUserForm, EditprofileForm
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


# เพิ่ม route ใหม่
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
    """
    โหลดหน้าเพิ่มฟอร์มใหม่ พร้อมรองรับ default scope และ sub scope
    """
    default_scope = request.args.get("default_scope", None)
    default_sub_scope = request.args.get("default_sub_scope", None)


    return render_template(
        "/form-management/add-form-and-formula.html",
        default_scope=default_scope,
        default_sub_scope=default_sub_scope,
    )


# อัปเดต edit_form_and_formula function เพื่อรองรับ scope
@module.route("/edit-form", methods=["POST"])
@login_required
def edit_form_and_formula():
    form_id = request.form.get("form_id")
    if not form_id:
        return jsonify({"success": False, "message": "No form ID provided"}), 400
    try:
        from bson import ObjectId

        form = FormAndFormula.objects(id=ObjectId(form_id)).first()
        if not form:
            return jsonify({"success": False, "message": "Form not found"}), 404

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
                return (
                    jsonify(
                        {"success": False, "message": "Sub Scope ต้องเป็นตัวเลขเท่านั้น"}
                    ),
                    400,
                )

        # ตรวจสอบว่าเป็นฟอร์มลิงก์หรือไม่ (ใช้ข้อมูลจาก database)
        is_linked = getattr(form, "is_linked", False)

        print(f"Debug - Current form is_linked: {is_linked}")
        print(f"Debug - Form linked_material_name: {getattr(form, 'linked_material_name', '')}")

        if is_linked:
            # ใช้ linked_material_name ที่มีอยู่แล้วใน database
            linked_material_name = getattr(form, "linked_material_name", "")
            
            if not linked_material_name:
                return (
                    jsonify(
                        {
                            "success": False, 
                            "message": "ฟอร์มลิงก์นี้ไม่มีการระบุ Material ต้นทาง กรุณาติดต่อผู้ดูแลระบบ"
                        }
                    ),
                    400,
                )
            
            # ดึงข้อมูล material ต้นฉบับ
            linked_material = FormAndFormula.objects(
                material_name=linked_material_name
            ).first()
            if not linked_material:
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": f"Material '{linked_material_name}' ไม่พบในระบบ กรุณาติดต่อผู้ดูแลระบบ",
                        }
                    ),
                    404,
                )

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

        # Flash message if you want it shown in the template
        flash("บันทึกการแก้ไขสำเร็จ!", "success")

        return redirect(url_for("form_management.form_management"))

        # return jsonify(
        #     {
        #         "success": True,
        #         "message": "บันทึกการแก้ไขสำเร็จ!",
        #         "redirect_url": url_for("form_management.form_management"),
        #     }
        #)
    except Exception as e:
        import traceback

        traceback.print_exc()
        return (
            jsonify({"success": False, "message": f"Failed to update form: {str(e)}"}),
            400,
        )


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
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"กรุณากรอกข้อมูลให้ครบถ้วน: {', '.join(missing_fields)}",
                    }
                ),
                400,
            )

        # ตรวจสอบชื่อวัสดุซ้ำ
        existing_material = FormAndFormula.objects(material_name=material_name).first()
        if existing_material:
            return jsonify(
                {
                    "success": False,
                    "message": f'ชื่อวัสดุ "{material_name}" มีอยู่แล้ว กรุณาใช้ชื่ออื่น',
                },
                409,
            )

        try:
            ghg_sup_scope_int = int(ghg_sup_scope)
        except ValueError:
            return (
                jsonify({"success": False, "message": "Sub Scope ต้องเป็นตัวเลขเท่านั้น"}),
                400,
            )

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
            is_linked=is_linked,  # เพิ่มบรรทัดนี้
            linked_material_name=linked_material_name if is_linked else "",  # เพิ่มบรรทัดนี้
        )

        print(f"Debug - new_form.is_linked: {new_form.is_linked}")
        print(f"Debug - new_form.linked_material_name: {new_form.linked_material_name}")

        if is_linked and linked_material_name:
            # ดึงข้อมูล material ต้นฉบับ
            linked_material = FormAndFormula.objects(
                material_name=linked_material_name
            ).first()
            if not linked_material:
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": f"Material '{linked_material_name}' ไม่พบในระบบ",
                        }
                    ),
                    404,
                )

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

        return jsonify(
            {
                "success": True,
                "message": "สร้างฟอร์มสำเร็จ!",
                "redirect_url": url_for("form_management.form_management"),
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "message": f"เกิดข้อผิดพลาด: {str(e)}"}), 400


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


@module.route("/get-available-materials/<int:scope>/<int:sub_scope>", methods=["GET"])
@login_required
def get_available_materials(scope, sub_scope):
    """
    ดึงรายชื่อ material ที่สามารถลิงก์ได้
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
