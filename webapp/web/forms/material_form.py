from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, IntegerField
from wtforms.validators import DataRequired, NumberRange
import datetime


class MaterialForm(FlaskForm):
    """Simplified Material Form for Pure HTMX"""

    # ✅ เก็บเฉพาะ fields ที่จำเป็น
    name = StringField("Name", validators=[DataRequired(message="ชื่อวัสดุจำเป็นต้องระบุ")])
    amount = FloatField(
        "Amount",
        validators=[
            DataRequired(message="จำนวนจำเป็นต้องระบุ"),
            NumberRange(min=0, message="จำนวนต้องมากกว่าหรือเท่ากับ 0"),
        ],
    )
    scope_id = IntegerField(
        "Scope ID", validators=[DataRequired(message="Scope ID จำเป็นต้องระบุ")]
    )
    sub_scope_id = IntegerField(
        "Sub Scope ID", validators=[DataRequired(message="Sub Scope ID จำเป็นต้องระบุ")]
    )
    year = IntegerField(
        "Year",
        validators=[
            DataRequired(message="ปีจำเป็นต้องระบุ"),
            NumberRange(
                min=2020,
                max=datetime.datetime.now().year + 1,
                message=f"ปีต้องอยู่ระหว่าง 2020-{datetime.datetime.now().year + 1}",
            ),
        ],
    )
    month_id = IntegerField(
        "Month",
        validators=[
            DataRequired(message="เดือนจำเป็นต้องระบุ"),
            NumberRange(min=1, max=12, message="เดือนต้องอยู่ระหว่าง 1-12"),
        ],
    )

    # ลบ methods ที่ซ้ำซ้อน - ใช้ WTForms validators แทน


# ✅ เก็บเฉพาะ helper function ที่จำเป็น
def validate_material_data(form_data, mode="single"):
    """Simplified validation using WTForms"""

    if mode == "single":
        # ✅ เพิ่ม type conversion สำหรับโหมดปกติ
        try:
            amount = form_data.get("amount")
            if amount is not None:
                amount = float(amount) if amount != "" else None

            scope_id = form_data.get("scope_id")
            if scope_id is not None:
                scope_id = int(scope_id)

            sub_scope_id = form_data.get("sub_scope_id")
            if sub_scope_id is not None:
                sub_scope_id = int(sub_scope_id)

            year = form_data.get("year")
            if year is not None:
                year = int(year)

            month_id = form_data.get("month_id")
            if month_id is not None:
                month_id = int(month_id)

        except (ValueError, TypeError) as e:
            return False, [f"ข้อมูลไม่ถูกต้อง: {str(e)}"]

        # ตรวจสอบข้อมูลพื้นฐาน
        errors = []

        if not form_data.get("head"):
            errors.append("ชื่อวัสดุจำเป็นต้องระบุ")

        if amount is None or amount == "":
            errors.append("จำนวนจำเป็นต้องระบุ")
        elif amount < 0:
            errors.append("จำนวนต้องมากกว่าหรือเท่ากับ 0")

        if not scope_id:
            errors.append("Scope ID จำเป็นต้องระบุ")

        if not sub_scope_id:
            errors.append("Sub Scope ID จำเป็นต้องระบุ")

        if not year or year < 2020 or year > datetime.datetime.now().year + 1:
            errors.append(f"ปีต้องอยู่ระหว่าง 2020-{datetime.datetime.now().year + 1}")

        if not month_id or month_id < 1 or month_id > 12:
            errors.append("เดือนต้องอยู่ระหว่าง 1-12")

        return len(errors) == 0, errors

    elif mode == "quick_edit":
        # Handle quick edit validation
        errors = []
        for key, value in form_data.items():
            if key.startswith("amount_") and value and str(value).strip():
                try:
                    amount = float(value)
                    if amount < 0:
                        parts = key.replace("amount_", "").split("_", 2)
                        material_name = parts[1] if len(parts) > 1 else "วัสดุ"
                        errors.append(f"{material_name}: จำนวนต้องมากกว่าหรือเท่ากับ 0")
                except (ValueError, TypeError):
                    parts = key.replace("amount_", "").split("_", 2)
                    material_name = parts[1] if len(parts) > 1 else "วัสดุ"
                    errors.append(f"{material_name}: จำนวนต้องเป็นตัวเลข")

        return len(errors) == 0, errors

    elif mode == "multiple":
        # ✅ เพิ่ม validation สำหรับโหมด materials-form.html (หลายตัว)
        errors = []
        has_data = False

        # ตรวจสอบว่ามี amount fields หรือไม่
        for key, value in form_data.items():
            if key.startswith("amount_") and value and str(value).strip():
                has_data = True
                try:
                    amount = float(value)
                    if amount < 0:
                        # แยก key pattern: amount_head_field
                        parts = key.replace("amount_", "").split("_")
                        if len(parts) >= 2:
                            material_name = parts[0]
                            field_name = "_".join(
                                parts[1:]
                            )  # รวม parts ที่เหลือเป็น field name
                        else:
                            material_name = parts[0] if parts else "วัสดุ"
                            field_name = "ฟิลด์"
                        errors.append(
                            f"{material_name} ({field_name}): จำนวนต้องมากกว่าหรือเท่ากับ 0"
                        )
                except (ValueError, TypeError):
                    # แยก key pattern: amount_head_field
                    parts = key.replace("amount_", "").split("_")
                    if len(parts) >= 2:
                        material_name = parts[0]
                        field_name = "_".join(
                            parts[1:]
                        )  # รวม parts ที่เหลือเป็น field name
                    else:
                        material_name = parts[0] if parts else "วัสดุ"
                        field_name = "ฟิลด์"
                    errors.append(f"{material_name} ({field_name}): จำนวนต้องเป็นตัวเลข")

        if not has_data:
            errors.append("กรุณากรอกข้อมูลอย่างน้อย 1 ฟิลด์")

        # ✅ ไม่ต้องตรวจสอบ head และ amount แบบ single mode ใน multiple mode
        # เพราะข้อมูลอยู่ในรูปแบบ amount_head_field แทน

        # ตรวจสอบ scope และ year ใน multiple mode
        try:
            scope_id = form_data.get("scope_id")
            sub_scope_id = form_data.get("sub_scope_id")
            year = form_data.get("year")
            month_id = form_data.get("month_id")

            if scope_id:
                scope_id = int(scope_id)
            if sub_scope_id:
                sub_scope_id = int(sub_scope_id)
            if year:
                year = int(year)
            if month_id:
                month_id = int(month_id)

            if not scope_id:
                errors.append("Scope ID จำเป็นต้องระบุ")
            if not sub_scope_id:
                errors.append("Sub Scope ID จำเป็นต้องระบุ")
            if not year:
                errors.append("ปีจำเป็นต้องระบุ")
            if not month_id:
                errors.append("เดือนจำเป็นต้องระบุ")

        except (ValueError, TypeError) as e:
            errors.append(f"ข้อมูลไม่ถูกต้อง: {str(e)}")

        return len(errors) == 0, errors

    return True, []
