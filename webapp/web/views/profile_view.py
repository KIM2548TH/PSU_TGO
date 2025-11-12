from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from flask_login import login_required, logout_user, current_user
from ..forms.user_form import LoginForm, RegisterForm, EditUserForm, EditprofileForm
from ...services.user_service import UserService
from ...models import User, Role, Permission, CampusAndDepartment

module = Blueprint("profile", __name__, url_prefix="/profile")

@module.route("/", methods=["get", "post"])
@login_required
def profile():
    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(user.campus_id,user.department_key)

    print(user.campus)
    return render_template("/profile/profile.html", user=user)


@module.route("/load-edit-profile", methods=["GET", "POST"])
@login_required
def load_edit_profile():
    user = current_user  # ใช้ current_user เพื่อดึงข้อมูลผู้ใช้ที่ล็อกอินอยู่
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(user.campus_id,user.department_key)
    if not user:
        return jsonify({"error": "User not found"}), 404

    form = EditprofileForm()
    if request.method == "POST":
        # กรอกข้อมูลจากฟอร์ม (ไม่รวม campus และ department)
        form.username.data = user.username  # ไม่ให้แก้ไข username
        form.name.data = request.form.get("name")  # เพิ่มฟิลด์ name
        form.email.data = request.form.get("email")
        # เก็บ campus และ department เดิมไว้ (ไม่ให้แก้ไข)
        form.campus.data = user.campus
        form.department.data = user.department

        # เรียกใช้ UserService เพื่อแก้ไขข้อมูล
        edit_result = UserService.edit_profile(form)
        if not edit_result["success"]:
            return render_template(
                "/profile/form-edit-profile.html",
                user=user,
                form=form,
                error_msg=edit_result["error_msg"],
            )
        return redirect(url_for("profile.profile"))

    # แสดงฟอร์มพร้อมข้อมูลผู้ใช้งาน
    form.username.data = user.username
    form.name.data = user.name  # เพิ่มฟิลด์ name
    form.email.data = user.email
    form.campus.data = user.campus
    form.department.data = user.department

    return render_template(
        "/profile/form-edit-profile.html",
        user=user,
        form=form,
    )


@module.route("/load-check-password-form", methods=["GET"])
@login_required
def load_check_password_form():
    return render_template("/profile/form-check-password.html")

@module.route("/check-current-password", methods=["POST"])
@login_required
def check_current_password():
    current_password = request.form.get("current_password")
    if not current_user.check_password(current_password):
        return render_template("/profile/form-check-password.html", error_msg="รหัสผ่านไม่ถูกต้อง")
    return render_template("/profile/form-new-password.html")

@module.route("/change-new-password", methods=["POST"])
@login_required
def change_new_password():
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")
    if new_password != confirm_password:
        return render_template("/profile/form-new-password.html", error_msg="รหัสผ่านไม่ตรงกัน")
    
    result = UserService.change_password(new_password)
    if not result["success"]:
        return render_template("/profile/form-new-password.html", error_msg=result["error_msg"])
    
    return render_template("success/success.html")