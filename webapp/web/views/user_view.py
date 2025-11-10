from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    jsonify,
    session,
    make_response,
)
from flask_login import login_required, logout_user, current_user
from ..forms.user_form import LoginForm, RegisterForm, EditUserForm, EditprofileForm
from ...services.user_service import UserService
from ...models import User, Role, Permission, CampusAndDepartment


module = Blueprint("users", __name__, url_prefix="/users")


# @module.route("/login", methods=["GET", "POST"])
# def login():
#     form = LoginForm()
#     error_msg = ""

#     # 🔹 STEP 1: โหลดค่า username ล่าสุดจาก cookie ถ้าเป็น GET
#     if request.method == "GET":
#         last_username = request.cookies.get("last_username", "")
#         form.username.data = last_username
        
#         return render_template("/users/login.html", form=form, error_msg=error_msg)

#     # 🔹 STEP 2: Validate form
#     if not form.validate_on_submit():
#         if "password" in form.errors:
#             if "Field must be at least 6 characters long." in form.errors["password"]:
#                 error_msg = "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"
#             elif "This field is required." in form.errors["password"]:
#                 error_msg = "กรุณากรอกรหัสผ่าน"
#             else:
#                 error_msg = "เกิดข้อผิดพลาดในการป้อนรหัสผ่าน"
#         return render_template("/users/login.html", form=form, error_msg=error_msg)

#     # 🔹 STEP 3: Authenticate user
#     login_result = UserService.login(form.username.data, form.password.data)
#     if not login_result["success"]:
#         return render_template(
#             "/users/login.html", form=form, error_msg=login_result["error_msg"]
#         )

#     # 🔹 STEP 4: ตั้งค่า cookie ใหม่เมื่อ login สำเร็จ
#     response = make_response(redirect(request.args.get("next", url_for("index.index"))))
#     response.set_cookie(
#         "last_username", form.username.data, max_age=60 * 60 * 24 * 30
#     )  # 30 วัน
#     return response
@module.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    error_msg = ""

    if request.method == "GET":
        last_username = request.cookies.get("last_username", "")
        form.username.data = last_username
        return render_template("/users/login.html", form=form, error_msg=error_msg)

    if not form.validate_on_submit():
        if "password" in form.errors:
            if "Field must be at least 6 characters long." in form.errors["password"]:
                error_msg = "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"
            elif "This field is required." in form.errors["password"]:
                error_msg = "กรุณากรอกรหัสผ่าน"
            else:
                error_msg = "เกิดข้อผิดพลาดในการป้อนรหัสผ่าน"
        return render_template("/users/login.html", form=form, error_msg=error_msg)

    # Authenticate user
    login_result = UserService.login(form.username.data, form.password.data)
    if not login_result["success"]:
        return render_template(
            "/users/login.html", form=form, error_msg=login_result["error_msg"]
        )

    # ✅ STEP 4: Save user info in session
    session["user_id"] = str(login_result["user"]["_id"])
    session["username"] = login_result["user"]["username"]
    session["role"] = login_result["user"]["role"]
    # 🔹 debug session content
    print("🟢 Session after login:", dict(session))

    # ✅ STEP 5: Set cookie for last_username
    response = make_response(redirect(request.args.get("next", url_for("index.index"))))
    response.set_cookie("last_username", form.username.data, max_age=60 * 60 * 24 * 30)  
    return response


@module.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("users.login"))


@module.route("/register", methods=["GET", "POST"])
@login_required
def register():
    form = RegisterForm()
    error_msg = ""
    campuses = CampusAndDepartment.objects()
    departments = campuses[0].departments if campuses else {}

    if request.method == "POST":
        campus_id = request.form.get("campus")
        department_key = request.form.get("department")
        form.campus_id = campus_id
        form.department_key = department_key

        register_result = UserService.register(form)
        if not register_result["success"]:
            return render_template(
                "/users/register.html",
                form=form,
                error_msg=register_result["error_msg"],
                campuses=campuses,
                departments=departments,
            )
        return redirect(url_for("users.login"))

    return render_template(
        "/users/register.html",
        form=form,
        error_msg=error_msg,
        campuses=campuses,
        departments=departments,
    )


@module.route("/load-departments-for-register", methods=["GET"])
@login_required
def load_departments_for_register():
    campus_id = request.args.get("campus")
    print("campus_id:", campus_id)  # Debug
    campus_obj = CampusAndDepartment.objects.with_id(campus_id)
    departments = campus_obj.departments if campus_obj else {}
    print("departments:", departments)  # Debug
    return render_template(
        "/users/partials/department_dropdown.html", departments=departments
    )
