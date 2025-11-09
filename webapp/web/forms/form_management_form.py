from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, IntegerField, HiddenField, FieldList, FormField
from wtforms.validators import DataRequired, Optional


class InputFieldForm(FlaskForm):
    field = StringField("Field", validators=[DataRequired()])
    label = StringField("Label", validators=[DataRequired()])
    input_type = SelectField("Input Type", 
                            choices=[('number', 'Number'), ('text', 'Text'), ('select', 'Select')],
                            validators=[DataRequired()])
    unit = StringField("Unit", validators=[Optional()])


class FormAndFormulaForm(FlaskForm):
    # Basic Info
    material_name = StringField("Material Name", validators=[DataRequired()])
    desc_form = TextAreaField("Form Description", validators=[DataRequired()])
    desc_formula = TextAreaField("Formula Description", validators=[DataRequired()])
    desc_formula2 = TextAreaField("Formula Description 2", validators=[Optional()])
    
    # Scope Selection
    scope = SelectField("Main Scope", 
                       choices=[(1, 'Scope 1'), (2, 'Scope 2'), (3, 'Scope 3')],
                       coerce=int, validators=[DataRequired()])
    sup_scope = SelectField("Sub Scope", coerce=int, validators=[DataRequired()])
    
    # Formula
    formula = StringField("Formula", validators=[DataRequired()])
    formula2 = StringField("Formula 2", validators=[Optional()])
    
    # Dynamic Input Fields (จะจัดการผ่าน HTMX)
    input_fields = FieldList(FormField(InputFieldForm), min_entries=0)
    
    # Hidden Fields
    form_id = HiddenField()