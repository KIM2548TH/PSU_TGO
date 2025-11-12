from ..models.user_model import User, get_all_sub_scopes
from flask_login import login_user, logout_user, current_user
from ..web.forms.user_form import RegisterForm, EditUserForm, EditprofileForm
import datetime


class UserService:
    @staticmethod
    def login(username: str, password: str):
        user = User.objects(username=username).first()
        error_msg = ""

        if not user or not user.check_password(password):
            error_msg = "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"
        elif user.status == "disactive":
            error_msg = "บัญชีของท่านถูกลบออกจากระบบ"

        if error_msg:
            return {"error_msg": error_msg, "success": False}

        login_user(user)  # if using Flask-Login
        user.last_login_date = datetime.datetime.now()
        user.save()

        # ✅ Return user info so you can save in session
        return {
            "error_msg": "",
            "success": True,
            "user": {
                "_id": str(user.id),
                "username": user.username,
                "name": user.name,  # เพิ่ม name
                "role": user.roles[0]
            }
        }


    @staticmethod
    def register(form: RegisterForm):
        username = form.username.data
        existing_user = User.objects(username=username).first()
        if existing_user:
            return {"success": False, "error_msg": "ชื่อผู้ใช้ซ้ำ"}

        if form.password.data != form.confirm_password.data:
            return {"success": False, "error_msg": "รหัสผ่านไม่ตรงกัน"}

        # Get sub scopes for each ghg_scope separately
        from ..models.user_model import get_sub_scopes_by_scope
        
        scope_1_subs = get_sub_scopes_by_scope(1)
        scope_2_subs = get_sub_scopes_by_scope(2) 
        scope_3_subs = get_sub_scopes_by_scope(3)

        user = User(
            username=form.username.data,
            name=form.name.data,  # เพิ่มฟิลด์ name
            roles=["user"],
            status="active",
            created_date=datetime.datetime.now(),
            updated_date=datetime.datetime.now(),
            campus_id=form.campus_id,
            department_key=form.department_key,
            # เซ็ตซับสโคปแยกตาม ghg_scope
            ghg_scope_1=scope_1_subs,
            ghg_scope_2=scope_2_subs,
            ghg_scope_3=scope_3_subs,
        )
        user.set_password(form.password.data)  # เข้ารหัสรหัสผ่าน
        user.save()
        return {"success": True, "error_msg": ""}

    @staticmethod
    def edit_user(form: EditUserForm):
        user = User.objects(username=form.username.data).first()
        if not user:
            return {"success": False, "error_msg": "ไม่พบผู้ใช้"}

        # อัปเดตฟิลด์ name
        user.name = form.name.data if form.name.data else user.name

        # ตรวจสอบและเซฟ campus_id
        user.campus_id = (
            form.campus.data
            if form.campus.data and form.campus.data != "none"
            else None
        )

        # ตรวจสอบและเซฟ department_key
        user.department_key = (
            form.department.data
            if form.department.data and form.department.data != "none"
            else None
        )
        user.email = form.email.data if form.email.data else user.email
        # เซฟข้อมูลอื่น ๆ
        user.roles = form.roles.data.split(",")
        user.save()
        return {"success": True, "error_msg": ""}

    @staticmethod
    def edit_profile(form: EditprofileForm):
        user = User.objects(id=current_user.id).first()
        if not user:
            return {"success": False, "error_msg": "ไม่พบผู้ใช้"}

        # อัปเดตเฉพาะ name และ email (ไม่ให้แก้ไข username)
        user.name = form.name.data
        user.email = form.email.data
        # campus และ department จะไม่ให้แก้ไขใน profile
        user.save()
        return {"success": True, "error_msg": ""}

    @staticmethod
    def est_password(username: str, password: str):
        user = User.objects(username=username).first()
        pass

        return {"success": True, "error_msg": ""}

    @staticmethod
    def change_password(new_password: str):
        user = User.objects(id=current_user.id).first()
        if not user:
            return {"success": False, "error_msg": "ไม่พบผู้ใช้"}

        user.set_password(new_password)
        user.save()
        return {"success": True, "error_msg": ""}
