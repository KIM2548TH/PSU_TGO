from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, IntegerField, HiddenField, FieldList, FormField, BooleanField, RadioField
from wtforms.validators import DataRequired, Optional, Length, ValidationError
from ...models import FormAndFormula, Scope


class InputFieldForm(FlaskForm):
    """Sub-form สำหรับ input fields"""
    field = StringField("Field Name", validators=[
        DataRequired(message="กรุณากรอกชื่อฟิลด์"),
        Length(min=1, max=50, message="ชื่อฟิลด์ต้องมีความยาว 1-50 ตัวอักษร")
    ])
    label = StringField("Label", validators=[
        DataRequired(message="กรุณากรอก Label"),
        Length(min=1, max=100, message="Label ต้องมีความยาว 1-100 ตัวอักษร")
    ])
    input_type = SelectField("Input Type", 
                            choices=[('number', 'Number'), ('text', 'Text'), ('select', 'Select')],
                            validators=[DataRequired(message="กรุณาเลือกประเภท Input")])
    unit = StringField("Unit", validators=[
        Optional(),
        Length(max=20, message="หน่วยต้องมีความยาวไม่เกิน 20 ตัวอักษร")
    ])


class FormAndFormulaForm(FlaskForm):
    """Main form สำหรับการจัดการ Form และ Formula"""
    
    # Basic Information
    material_name = StringField("Material Name", validators=[
        DataRequired(message="กรุณากรอกชื่อวัสดุ"),
        Length(min=1, max=100, message="ชื่อวัสดุต้องมีความยาว 1-100 ตัวอักษร")
    ])
    
    desc_form = TextAreaField("Form Description", validators=[
        Optional(),
        Length(max=500, message="คำอธิบายฟอร์มต้องมีความยาวไม่เกิน 500 ตัวอักษร")
    ])
    
    # Scope Selection
    scope = SelectField("Main Scope", 
                       choices=[(1, 'Scope 1'), (2, 'Scope 2'), (3, 'Scope 3')],
                       coerce=int, 
                       validators=[DataRequired(message="กรุณาเลือก Main Scope")])
    
    sup_scope = SelectField("Sub Scope", 
                           coerce=int, 
                           validators=[DataRequired(message="กรุณาเลือก Sub Scope")])
    
    # Form Type
    form_type = RadioField("Form Type",
                          choices=[('normal', 'ฟอร์มปกติ'), ('linked', 'ฟอร์มลิงก์')],
                          default='normal',
                          validators=[DataRequired(message="กรุณาเลือกประเภทฟอร์ม")])
    
    # Linked Form Fields
    linked_material_name = SelectField("Linked Material", 
                                     choices=[],
                                     validators=[Optional()])
    
    # Formula
    formula = StringField("Formula", validators=[
        DataRequired(message="กรุณากรอกสูตรคำนวณ"),
        Length(min=1, max=200, message="สูตรต้องมีความยาว 1-200 ตัวอักษร")
    ])
    
    formula2 = StringField("Formula 2", validators=[
        Optional(),
        Length(max=200, message="สูตรที่ 2 ต้องมีความยาวไม่เกิน 200 ตัวอักษร")
    ])
    
    desc_formula = TextAreaField("Formula Description", validators=[
        Optional(),
        Length(max=500, message="คำอธิบายสูตรต้องมีความยาวไม่เกิน 500 ตัวอักษร")
    ])
    
    desc_formula2 = TextAreaField("Formula 2 Description", validators=[
        Optional(),
        Length(max=500, message="คำอธิบายสูตรที่ 2 ต้องมีความยาวไม่เกิน 500 ตัวอักษร")
    ])
    
    # Hidden Fields
    form_id = HiddenField()
    is_linked = HiddenField()
    
    def __init__(self, *args, **kwargs):
        super(FormAndFormulaForm, self).__init__(*args, **kwargs)
        self._populate_choices()
    
    def _populate_choices(self):
        """โหลด choices สำหรับ dropdown fields"""
        # โหลด available materials สำหรับ linked form
        available_materials = FormAndFormula.objects(is_linked=False).order_by('material_name')
        self.linked_material_name.choices = [('', 'เลือก Material')] + [
            (material.material_name, f"{material.material_name} (Scope {material.ghg_scope}.{material.ghg_sup_scope})")
            for material in available_materials
        ]
    
    def validate_material_name(self, field):
        """ตรวจสอบชื่อวัสดุซ้ำ"""
        existing = FormAndFormula.objects(material_name=field.data).first()
        if existing and str(existing.id) != self.form_id.data:
            raise ValidationError('ชื่อวัสดุนี้มีอยู่แล้ว กรุณาใช้ชื่ออื่น')
    
    def validate_linked_material_name(self, field):
        """ตรวจสอบ linked material เมื่อเป็น linked form"""
        if self.form_type.data == 'linked' and not field.data:
            raise ValidationError('กรุณาเลือก Material ที่ต้องการเชื่อมโยง')
    
    def validate_sup_scope(self, field):
        """ตรวจสอบ Sub Scope ว่ามีอยู่จริง"""
        if self.scope.data and field.data:
            scope_exists = Scope.objects(
                ghg_scope=self.scope.data,
                ghg_sup_scope=field.data
            ).first()
            if not scope_exists:
                raise ValidationError('Sub Scope ที่เลือกไม่ถูกต้อง')


class EditFormAndFormulaForm(FormAndFormulaForm):
    """Form สำหรับการแก้ไข (ไม่ให้เปลี่ยน scope)"""
    
    def __init__(self, *args, **kwargs):
        super(EditFormAndFormulaForm, self).__init__(*args, **kwargs)
        # ปิดการแก้ไข scope fields
        self.scope.render_kw = {'disabled': True}
        self.sup_scope.render_kw = {'disabled': True}