from flask import Blueprint, render_template, redirect, url_for, request, jsonify, make_response
from flask_login import login_required, current_user
from ..forms.user_form import RegisterForm
from ...services.user_service import UserService
from ...models import User, CampusAndDepartment
from ...models.scope_model import Scope
from ..utils.acl import permissions_required_all

module = Blueprint("department_management", __name__, url_prefix="/department-management")


@module.route("/", methods=["GET"])
@login_required
@permissions_required_all(["เข้าถึงหน้าจัดการผู้ใช้ในหน่วยงาน"])
def department_management():
    """
    แสดงหน้าจัดการผู้ใช้ในแผนกเดียวกัน
    เฉพาะผู้ใช้ในแผนกเดียวกันเท่านั้น
    """
    try:
        # ดึงผู้ใช้ในแผนกเดียวกันเท่านั้น
        users = User.objects(
            campus_id=current_user.campus_id,
            department_key=current_user.department_key
        )
        
        for user in users:
            user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
            user.department = CampusAndDepartment.get_department_name(
                user.campus_id, user.department_key
            )

        # ดึงข้อมูล campus และ department ของผู้ใช้ปัจจุบัน
        current_campus = CampusAndDepartment.get_campus_name(current_user.campus_id)
        current_department = CampusAndDepartment.get_department_name(
            current_user.campus_id, current_user.department_key
        )

        # เพิ่มข้อมูลชื่อ scope สำหรับแสดงผล
        _add_scope_display_names(users)

        # คำนวณ pagination
        total_users = users.count()
        per_page = 10
        total_pages = (total_users + per_page - 1) // per_page

        return render_template(
            "/department-management/department-management.html",
            users=users,
            current_campus=current_campus,
            current_department=current_department,
            page=1,  # เพิ่มตัวแปร page
            total_pages=total_pages,  # เพิ่มตัวแปร total_pages
        )
    except Exception as e:
        return render_template(
            "/department-management/department-management.html",
            users=[],
            current_campus="",
            current_department="",
            page=1,  # เพิ่มตัวแปร page
            total_pages=1,  # เพิ่มตัวแปร total_pages
            error=f"เกิดข้อผิดพลาด: {str(e)}"
        )


@module.route("/load-edit-user-scopes/<user_id>", methods=["GET"])
@login_required
@permissions_required_all(["แก้ไขข้อมูลผู้ใช้ในหน่วยงาน"])
def load_edit_user_scopes(user_id):
    """
    โหลดฟอร์มแก้ไข scope ย่อยและ status ของผู้ใช้ (สำหรับ HTMX popup)
    """
    try:
        user = User.objects.with_id(user_id)
        if not user:
            return '<div class="p-4 text-red-700 bg-red-100 border border-red-400 rounded">ไม่พบผู้ใช้</div>', 404

        # ตรวจสอบว่าผู้ใช้อยู่ในแผนกเดียวกันหรือไม่
        if user.campus_id != current_user.campus_id or user.department_key != current_user.department_key:
            return '<div class="p-4 text-red-700 bg-red-100 border border-red-400 rounded">ไม่มีสิทธิ์เข้าถึง</div>', 403

        # ดึงข้อมูล scope จาก base template พร้อมชื่อ
        base_scopes = Scope.objects(campus="base", department="base").order_by("ghg_scope", "ghg_sup_scope")
        
        # จัดกลุ่ม scope ตาม ghg_scope
        scopes_by_type = {1: {}, 2: {}, 3: {}}
        scope_names = {1: "", 2: "", 3: ""}  # ชื่อ scope หลัก
        
        # หาชื่อ scope หลักก่อน (scope ที่มี ghg_sup_scope = ghg_scope)
        for scope_type in [1, 2, 3]:
            main_scope = Scope.objects(
                campus="base", 
                department="base", 
                ghg_scope=scope_type, 
                ghg_sup_scope=scope_type
            ).first()
            if main_scope:
                scope_names[scope_type] = main_scope.ghg_name
            else:
                scope_names[scope_type] = f"Scope {scope_type}"
        
        # จัดกลุ่ม sub-scopes
        for scope in base_scopes:
            if scope.ghg_scope in scopes_by_type:
                scopes_by_type[scope.ghg_scope][scope.ghg_sup_scope] = {
                    'id': scope.ghg_sup_scope,
                    'name': scope.ghg_name
                }

        return render_template(
            "/department-management/partials/edit_user_scopes_form.html",
            user=user,
            scopes_by_type=scopes_by_type,
            scope_names=scope_names,
        )

    except Exception as e:
        return f'<div class="p-4 text-red-700 bg-red-100 border border-red-400 rounded">เกิดข้อผิดพลาด: {str(e)}</div>', 500


@module.route("/update-user-scopes/<user_id>", methods=["POST"])
@login_required  
@permissions_required_all(["แก้ไขข้อมูลผู้ใช้ในหน่วยงาน"])
def update_user_scopes(user_id):
    """
    อัปเดต scope ย่อยของผู้ใช้
    """
    try:
        user = User.objects.with_id(user_id)
        if not user:
            response = make_response("")
            response.headers['HX-Trigger'] = '{"showError": "User not found"}'
            return response

        # ตรวจสอบสิทธิ์
        if user.campus_id != current_user.campus_id or user.department_key != current_user.department_key:
            response = make_response("")
            response.headers['HX-Trigger'] = '{"showError": "Access denied"}'
            return response

        # รับข้อมูลจาก HTML form โดยตรง (ไม่ใช้ Flask-WTF)
        ghg_scope_1 = request.form.getlist('ghg_scope_1')  # รับ list ของ checkbox values
        ghg_scope_2 = request.form.getlist('ghg_scope_2')
        ghg_scope_3 = request.form.getlist('ghg_scope_3')
        new_status = request.form.get('status')

        # แปลง string values เป็น integers
        user.ghg_scope_1 = [int(x) for x in ghg_scope_1 if x.isdigit()]
        user.ghg_scope_2 = [int(x) for x in ghg_scope_2 if x.isdigit()]
        user.ghg_scope_3 = [int(x) for x in ghg_scope_3 if x.isdigit()]
        
        # อัปเดต status ของผู้ใช้
        if new_status in ['active', 'disactive']:
            user.status = new_status
        
        user.save()

        # รีโหลดตารางผู้ใช้พร้อมแสดง toast success
        users = User.objects(
            campus_id=current_user.campus_id,
            department_key=current_user.department_key
        )
        
        for u in users:
            u.campus = CampusAndDepartment.get_campus_name(u.campus_id)
            u.department = CampusAndDepartment.get_department_name(
                u.campus_id, u.department_key
            )

        # เพิ่มข้อมูลชื่อ scope สำหรับแสดงผล
        _add_scope_display_names(users)

        response = make_response(render_template(
            "/department-management/users-table.html",
            users=users,
            page=1,
            total_pages=1,
        ))
        
        # ใช้ข้อความภาษาอังกฤษทั้งหมด
        response.headers['HX-Trigger'] = '{"showSuccess": "User scope updated successfully", "closeModal": true}'
        return response

    except Exception as e:
        response = make_response("")
        response.headers['HX-Trigger'] = f'{{"showError": "An error occurred: {str(e)}"}}'
        return response


def _add_scope_display_names(users):
    """เพิ่มชื่อ scope สำหรับแสดงผลในตาราง"""
    base_scopes = Scope.objects(campus="base", department="base")
    scope_names = {}
    
    for scope in base_scopes:
        key = f"{scope.ghg_scope}_{scope.ghg_sup_scope}"
        scope_names[key] = scope.ghg_name
    
    # เพิ่มชื่อ scope ให้กับแต่ละผู้ใช้
    for user in users:
        user.ghg_scope_1_names = []
        user.ghg_scope_2_names = []
        user.ghg_scope_3_names = []
        
        # Scope 1
        for sub_scope in (user.ghg_scope_1 or []):
            key = f"1_{sub_scope}"
            name = scope_names.get(key, f"Scope 1.{sub_scope}")
            user.ghg_scope_1_names.append({"id": sub_scope, "name": name})
        
        # Scope 2
        for sub_scope in (user.ghg_scope_2 or []):
            key = f"2_{sub_scope}"
            name = scope_names.get(key, f"Scope 2.{sub_scope}")
            user.ghg_scope_2_names.append({"id": sub_scope, "name": name})
        
        # Scope 3
        for sub_scope in (user.ghg_scope_3 or []):
            key = f"3_{sub_scope}"
            name = scope_names.get(key, f"Scope 3.{sub_scope}")
            user.ghg_scope_3_names.append({"id": sub_scope, "name": name})


@module.route("/load-users-table", methods=["GET"])
@login_required
@permissions_required_all(["เข้าถึงหน้าจัดการผู้ใช้ในหน่วยงาน"])
def load_users_table():
    """
    โหลดตารางผู้ใช้ในแผนกเดียวกัน (สำหรับการค้นหา)
    """
    try:
        page = int(request.args.get("page", 1))
        per_page = 10
        search_query = request.args.get("search", "").strip()

        query = {
            "campus_id": current_user.campus_id,
            "department_key": current_user.department_key
        }
        
        if search_query:
            # ค้นหาจาก name หรือ username
            from mongoengine import Q
            search_filter = Q(name__icontains=search_query) | Q(username__icontains=search_query)
            users = User.objects(search_filter).filter(**query)
        else:
            users = User.objects(**query)

        total_users = users.count()
        total_pages = (total_users + per_page - 1) // per_page
        users = users.skip((page - 1) * per_page).limit(per_page)
        
        for user in users:
            user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
            user.department = CampusAndDepartment.get_department_name(
                user.campus_id, user.department_key
            )

        # เพิ่มข้อมูลชื่อ scope สำหรับแสดงผล
        _add_scope_display_names(users)

        return render_template(
            "/department-management/users-table.html",
            users=users,
            page=page,
            total_pages=total_pages,
            search_query=search_query,
        )
    except Exception as e:
        return f'<div class="p-4 text-red-700 bg-red-100 border border-red-400 rounded">เกิดข้อผิดพลาด: {str(e)}</div>', 500


@module.route("/load-register-form", methods=["GET"])
@login_required
@permissions_required_all(["สร้างผู้ใช้ใหม่ในหน่วยงาน"])
def load_register_form():
    """
    โหลดฟอร์มสร้างผู้ใช้ใหม่ (สำหรับ HTMX popup)
    """
    try:
        form = RegisterForm()
        
        # ดึงข้อมูล campus และ department ของผู้ใช้ปัจจุบัน
        current_campus = CampusAndDepartment.get_campus_name(current_user.campus_id)
        current_department = CampusAndDepartment.get_department_name(
            current_user.campus_id, current_user.department_key
        )

        return render_template(
            "/department-management/partials/register_form.html",
            form=form,
            current_campus=current_campus,
            current_department=current_department,
        )
    except Exception as e:
        return f'<div class="p-4 text-red-700 bg-red-100 border border-red-400 rounded">เกิดข้อผิดพลาด: {str(e)}</div>', 500


@module.route("/create-user", methods=["POST"])
@login_required
@permissions_required_all(["สร้างผู้ใช้ใหม่ในหน่วยงาน"])
def create_user():
    """
    สร้างผู้ใช้ใหม่ในแผนกเดียวกัน
    """
    try:
        form = RegisterForm()

        if form.validate_on_submit():
            # ใช้ campus และ department ของผู้ใช้ปัจจุบัน
            form.campus_id = current_user.campus_id
            form.department_key = current_user.department_key

            register_result = UserService.register(form)
            if register_result["success"]:
                # รีโหลดตารางผู้ใช้พร้อมแสดง toast success
                users = User.objects(
                    campus_id=current_user.campus_id,
                    department_key=current_user.department_key
                )
                
                for u in users:
                    u.campus = CampusAndDepartment.get_campus_name(u.campus_id)
                    u.department = CampusAndDepartment.get_department_name(
                        u.campus_id, u.department_key
                    )

                # เพิ่มข้อมูลชื่อ scope สำหรับแสดงผล
                _add_scope_display_names(users)

                response = make_response(render_template(
                    "/department-management/users-table.html",
                    users=users,
                    page=1,
                    total_pages=1,
                ))
                response.headers['HX-Trigger'] = '{"showSuccess": "User created successfully", "closeModal": true}'
                return response
            else:
                # แสดง error message
                response = make_response("")
                response.headers['HX-Trigger'] = f'{{"showError": "{register_result["error_msg"]}"}}'
                return response
        else:
            # แสดง error จาก form validation
            error_messages = []
            for field, errors in form.errors.items():
                for error in errors:
                    error_messages.append(f"{field}: {error}")
            
            response = make_response("")
            response.headers['HX-Trigger'] = f'{{"showError": "Invalid form data: {", ".join(error_messages)}"}}'
            return response

    except Exception as e:
        response = make_response("")
        response.headers['HX-Trigger'] = f'{{"showError": "An error occurred: {str(e)}"}}'
        return response