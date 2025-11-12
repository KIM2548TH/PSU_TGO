from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, EmailField, SelectField
from wtforms.validators import DataRequired


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])


class RegisterForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    name = StringField("Name", validators=[DataRequired()])  # เพิ่มฟิลด์ name
    password = PasswordField("Password", validators=[DataRequired()])
    confirm_password = PasswordField("Confirm Password", validators=[DataRequired()])


class EditUserForm(FlaskForm):
    username = StringField("Username")  # ลบ validators เพื่อไม่ให้แก้ไข username
    name = StringField("Name", validators=[DataRequired()])  # เพิ่มฟิลด์ name
    campus = SelectField("Campus", choices=[])  # ใช้ SelectField สำหรับ dropdown
    department = StringField("Department")
    email = EmailField("Email", validators=[DataRequired()])
    roles = StringField("Roles")
    # Add any other fields you need for editing the user


class EditprofileForm(FlaskForm):
    username = StringField("Username")  # ลบ validators เพื่อไม่ให้แก้ไข username
    name = StringField("Name", validators=[DataRequired()])  # เพิ่มฟิลด์ name
    email = EmailField("Email", validators=[DataRequired()])
    campus = StringField("Campus")
    department = StringField("Department")
