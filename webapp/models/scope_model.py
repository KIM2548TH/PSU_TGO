import mongoengine as me
import datetime


class Scope(me.Document):
    ghg_scope = me.IntField(required=True)  # Scope เช่น 1
    ghg_sup_scope = me.IntField(required=True)  # Scope หลัก เช่น 1
    ghg_name = me.StringField(required=True)  # ชื่อ GHG
    ghg_desc = me.StringField(required=False, default="")  # คำอธิบาย GHG
    campus = me.StringField(required=True)
    department = me.StringField(required=True)
    head_table = me.ListField(
        me.StringField(), default=[]
    )  # รายการหัวข้อ เช่น ["transport", "vehicle"]
    create_date = me.DateTimeField(default=datetime.datetime.now)  # วันที่สร้าง
    update_date = me.DateTimeField(default=datetime.datetime.now)  # วันที่อัปเดต

    @classmethod
    def clone_for_new_department(cls, campus_id, source_dept_key, target_dept_key):
        """Clone scope จากหน่วยงานต้นฉบับไปยังหน่วยงานใหม่"""
        try:
            # ดึง scope ทั้งหมดจากหน่วยงานต้นฉบับ
            source_scopes = cls.objects(campus=campus_id, department=source_dept_key)
            
            cloned_count = 0
            for scope in source_scopes:
                # สร้าง scope ใหม่
                new_scope = cls(
                    ghg_scope=scope.ghg_scope,
                    ghg_sup_scope=scope.ghg_sup_scope,
                    ghg_name=scope.ghg_name,
                    ghg_desc=scope.ghg_desc,
                    campus=campus_id,
                    department=target_dept_key,
                    head_table=scope.head_table.copy() if scope.head_table else [],
                    create_date=datetime.datetime.now(),
                    update_date=datetime.datetime.now()
                )
                new_scope.save()
                cloned_count += 1
            
            return cloned_count
            
        except Exception as e:
            print(f"Error cloning scopes: {e}")
            return 0

    @classmethod
    def find_department_with_scopes(cls, campus_id, exclude_dept_key=None):
        """หาหน่วยงานแรกที่มี scope ในวิทยาเขตนี้"""
        try:
            # หาหน่วยงานที่มี scope (ยกเว้นหน่วยงานที่ระบุ)
            query = {"campus": campus_id}
            if exclude_dept_key:
                query["department__ne"] = exclude_dept_key
            
            scope = cls.objects(**query).first()
            return scope.department if scope else None
            
        except Exception as e:
            print(f"Error finding department with scopes: {e}")
            return None

    @classmethod
    def handle_department_clone(cls, campus_id, new_dept_key, clone_from_dept=None):
        """จัดการการ clone scope สำหรับหน่วยงานใหม่"""
        if clone_from_dept == "":
            # User เลือก "ไม่คัดลอก Scope" - ไม่ทำอะไร
            return 0
        
        elif clone_from_dept is None:
            # ไม่ได้ระบุค่าจาก UI (legacy behavior) - หาอัตโนมัติ
            auto_clone_dept = cls.find_department_with_scopes(campus_id, exclude_dept_key=new_dept_key)
            
            if auto_clone_dept:
                cloned_count = cls.clone_for_new_department(campus_id, auto_clone_dept, new_dept_key)
                return cloned_count
            else:
                return 0
        
        else:
            # User เลือกหน่วยงานเฉพาะ
            # ตรวจสอบว่า source department มีอยู่จริงหรือไม่
            from .campus_and_department_model import CampusAndDepartment
            campus = CampusAndDepartment.objects(id=campus_id).first()
            
            if not campus or clone_from_dept not in campus.departments:
                return 0
            else:
                cloned_count = cls.clone_for_new_department(campus_id, clone_from_dept, new_dept_key)
                return cloned_count

    meta = {
        "collection": "scope",  # ชื่อคอลเลกชันใน MongoDB
        "indexes": ["ghg_scope", "ghg_sup_scope"],  # ดัชนีสำหรับการค้นหา
    }
