import mongoengine as me
import datetime
from bson import ObjectId


class UploadedFile(me.EmbeddedDocument):
    id = me.ObjectIdField(default=ObjectId, primary_key=True)  # เพิ่มฟิลด์ id
    filename = me.StringField(required=True)
    content_type = me.StringField(required=True)
    data = me.BinaryField(required=True)
    upload_date = me.DateTimeField(default=datetime.datetime.now)


class ReferenceDocument(me.Document):
    scope_id = me.IntField(required=True)
    sub_scope_id = me.IntField(required=True)
    year = me.IntField(required=True)
    month = me.IntField(required=True)
    campus = me.StringField(required=True)
    department = me.StringField(required=True)
    files = me.EmbeddedDocumentListField(UploadedFile)

    meta = {
        "collection": "reference_documents",
        "indexes": [
            "scope_id",
            "sub_scope_id",
            "year",
            "month",
            "campus",
            "department",
        ],
    }


class TemplateExcel(me.Document):
    campus_id = me.StringField(required=True)  # วิทยาเขต
    year = me.IntField(required=True)  # ปี (ไม่ unique เพราะ 1 ปีมีได้หลายไฟล์)
    display_name = me.StringField(required=True)  # ชื่อแสดง (แก้ไขได้)
    file = me.EmbeddedDocumentField(UploadedFile, required=True)
    sheet_name = me.StringField(default="Fr-04.1")  # ชื่อ sheet ที่จะใช้งาน
    uploaded_by = me.StringField(required=True)

    meta = {
        "collection": "template_excel",
        "indexes": ["year", "campus_id", "display_name"],
    }
