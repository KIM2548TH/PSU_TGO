from flask_wtf import FlaskForm
from wtforms import HiddenField, FieldList
from wtforms.validators import DataRequired

class MaterialMappingExcelForm(FlaskForm):
    csrf_token = HiddenField()
    # ฟิลด์สำหรับแต่ละ scope/sub-scope/sub-sub-scope จะถูกสร้างแบบไดนามิกใน view
    # ตัวอย่าง: material_1_subscope_subsubscope = FieldList(HiddenField())
    # สามารถเพิ่มฟิลด์แบบไดนามิกใน view

class FormChoicesModalForm(FlaskForm):
    csrf_token = HiddenField()
    form_choices = FieldList(HiddenField(validators=[DataRequired()]))