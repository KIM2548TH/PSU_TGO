from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Length, Regexp


class CampusForm(FlaskForm):
    campus_name = StringField(
        "ชื่อวิทยาเขต", 
        validators=[
            DataRequired(message="กรุณากรอกชื่อวิทยาเขต"),
            Length(min=2, max=100, message="ชื่อวิทยาเขตต้องมีความยาว 2-100 ตัวอักษร")
        ]
    )
    
    description = TextAreaField(
        "คำอธิบายวิทยาเขต",
        validators=[
            Length(max=500, message="คำอธิบายต้องไม่เกิน 500 ตัวอักษร")
        ]
    )


class DepartmentForm(FlaskForm):
    department_name = StringField(
        "ชื่อหน่วยงาน", 
        validators=[
            DataRequired(message="กรุณากรอกชื่อหน่วยงาน"),
            Length(min=2, max=150, message="ชื่อหน่วยงานต้องมีความยาว 2-150 ตัวอักษร")
        ]
    )