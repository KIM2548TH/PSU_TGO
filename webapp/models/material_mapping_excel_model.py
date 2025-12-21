import mongoengine as me
import datetime

class MaterialMappingExcel(me.Document):
    campus_id = me.StringField(required=True)
    department_key = me.StringField(required=True)
    year = me.IntField(required=True)
    sheet_name = me.StringField(required=True, default="Fr-04.1")
    template_excel_id = me.StringField()  # เก็บ ID ของ TemplateExcel ที่เลือกใช้
    # mappings: dict {ชื่อรายการ(คอลัมน์ B): [ {"id": <material_id>, "value": <amount>} ] }
    mappings = me.DictField()  # value เป็น list ของ dict
    created_date = me.DateTimeField(default=datetime.datetime.now)
    updated_date = me.DateTimeField(default=datetime.datetime.now)

    meta = {
        "collection": "material_mapping_excel",
        "indexes": ["campus_id", "department_key", "year", "sheet_name"],
    }
