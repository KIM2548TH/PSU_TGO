from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from flask_login import login_required, logout_user, current_user
from ..forms.user_form import LoginForm, RegisterForm, EditUserForm, EditprofileForm
from ...services.user_service import UserService
from ...models import User, Role, Permission
from ..utils.acl import permissions_required_all

module = Blueprint("role_management", __name__, url_prefix="/role-management")


@module.route("/", methods=["GET", "POST"])
@permissions_required_all(["เข้าถึงหน้าจัดการสิทธิ์"])
@login_required
def role_management():
    roles = Role.objects().order_by("rank")
    return render_template("/role-management/role-management.html", roles=roles)


@module.route("/load-add-role", methods=["GET"])
@login_required
@permissions_required_all(["เพิ่มบทบาท"])
def load_add_role():
    # ดึงข้อมูล Permission ทั้งหมดจากฐานข้อมูล
    permissions = Permission.objects()

    return render_template("/role-management/add-role.html", permissions=permissions)


@module.route("/add-role", methods=["POST"])
@login_required
@permissions_required_all(["เพิ่มบทบาท"])
def add_role():
    name = request.form.get("name")
    description = request.form.get("description")

    permissions = request.form.getlist("permissions")
    rank = request.form.get("rank", type=int) or 1
    scope_type = request.form.get("scope_type", "global")

    existing_role = Role.objects(name=name).first()
    if existing_role:
        permissions_list = Permission.objects()
        return render_template(
            "/role-management/add-role.html",
            error_msg="Role already exists",
            permissions=permissions_list,
        )

    try:
        role = Role(
            name=name,
            description=description,
            permission=permissions,
            rank=rank,
            scope_type=scope_type,
        )
        role.save()
    except Exception as e:
        permissions_list = Permission.objects()
        return render_template(
            "/role-management/add-role.html",
            error_msg=f"Failed to create role: {str(e)}",
            permissions=permissions_list,
        )

    # สำเร็จ → redirect ไป roles-management
    return redirect(url_for("role_management.role_management"))


@module.route("/load-edit-role/<role_id>", methods=["GET"])
@permissions_required_all(["แก้ไขบทบาท"])
@login_required
def load_edit_role(role_id):
    role = Role.objects(id=role_id).first()
    permissions = Permission.objects()

    # เตรียมรายการ permission.id ที่ถูกเลือกไว้แล้ว
    selected_permission_ids = [p.id for p in permissions if p.name in role.permission]

    return render_template(
        "/role-management/edit-role.html",
        role=role,
        permissions=permissions,
        selected_permission_ids=selected_permission_ids,
    )


@module.route("/edit-role/<role_id>", methods=["POST"])
@login_required
@permissions_required_all(["แก้ไขบทบาท"])
def edit_role(role_id):
    role = Role.objects(id=role_id).first()
    role.name = request.form.get("name")
    role.description = request.form.get("description")
    rank = request.form.get("rank", type=int) or 1
    scope_type = request.form.get("scope_type", "global")

    try:
        permission_ids = request.form.getlist("permissions")

        # แปลง ID ให้เป็น Permission object
        permissions = []
        for pid in permission_ids:
            permission = Permission.objects(id=pid).first()
            if permission:
                permissions.append(permission.name)

        role.permission = permissions
        role.rank = rank
        role.scope_type = scope_type
        role.save()

    except Exception as e:
        permissions = Permission.objects()
        return render_template(
            "/role-management/edit-role.html",
            role=role,
            permissions=permissions,
            error_msg=f"Error updating role: {str(e)}",
        )

    return render_template("/role-management/success.html")
