import mongoengine as me
import datetime

class CampusAndDepartment(me.Document):
    # name คือ ชื่อ campus ({"0":"hatyai"})
    name = me.DictField(required=True)
    # description คือ คำอธิบายของ campus
    description = me.StringField(default="")
    # departments เป็น dict: {"1": "president", "2": "IT Department", ...}
    departments = me.DictField(required=True)

    created_date = me.DateTimeField(required=True, default=datetime.datetime.now)
    updated_date = me.DateTimeField(required=True, default=datetime.datetime.now)

    def _has_related_data(self, campus_name):
        """ตรวจสอบว่ามีข้อมูลที่เกี่ยวข้องกับวิทยาเขตหรือไม่"""
        try:
            campus_id = str(self.id)
            
            # ตรวจสอบจาก User model (ใช้ campus_id ซึ่งเป็น ObjectId) - หยุดทันทีที่เจอ
            from .user_model import User
            user_exists = User.objects(campus_id=campus_id).first() is not None
            if user_exists:
                return True
            
            # ตรวจสอบจาก Scope model (ใช้ campus_id)
            from .scope_model import Scope
            scope_exists = Scope.objects(campus=campus_id).first() is not None
            if scope_exists:
                return True
            
            # ตรวจสอบจาก Material model - ใช้ campus_id แทนชื่อ
            from .materail_model import Material
            material_exists = Material.objects(campus=campus_id).first() is not None
            if material_exists:
                return True
            
            # ตรวจสอบจาก ReferenceDocument model
            from .file_model import ReferenceDocument
            file_exists = ReferenceDocument.objects(campus=campus_name).first() is not None
            if file_exists:
                return True
            
            return False  # ไม่เจอข้อมูลใดๆ
            
        except Exception as e:
            print(f"Error checking campus data: {e}")
            return True  # ป้องกันการลบเมื่อเกิดข้อผิดพลาด

    def _has_department_data(self, campus_name, dept_key):
        """ตรวจสอบว่ามีข้อมูลที่เกี่ยวข้องกับหน่วยงานหรือไม่"""
        try:
            dept_name = self.departments.get(dept_key, "")
            campus_id = str(self.id)
            
            # ตรวจสอบจาก User model - หยุดทันทีที่เจอ
            from .user_model import User
            user_exists = User.objects(campus_id=campus_id, department_key=dept_key).first() is not None
            if user_exists:
                return True  # หยุดทันทีถ้าเจอ
            
            # ตรวจสอบจาก Material model - เช็คว่ามี Material ที่มีข้อมูลจริงๆ หรือไม่
            from .materail_model import Material
            materials = Material.objects(campus=campus_id, department=dept_key)
            
            # เช็คว่ามี Material ที่มีข้อมูลจริงๆ (ไม่ใช่แค่ scope เปล่าๆ)
            for material in materials:
                # ถ้ามี quantity_type ที่มีข้อมูล หรือ result ที่ไม่เป็น None/empty
                has_meaningful_data = (
                    (material.quantity_type and len(material.quantity_type) > 0) or
                    (material.result is not None and material.result != "") or
                    (material.result2 is not None and material.result2 != "")
                )
                if has_meaningful_data:
                    return True  # มี Material ที่มีข้อมูลจริงๆ - ห้ามลบ
            
            # ตรวจสอบจาก ReferenceDocument model - ลองทั้ง key และ name
            from .file_model import ReferenceDocument
            file_exists_key = ReferenceDocument.objects(campus=campus_name, department=dept_key).first() is not None
            if file_exists_key:
                return True
                
            file_exists_name = ReferenceDocument.objects(campus=campus_name, department=dept_name).first() is not None
            if file_exists_name:
                return True
            
            return False  # ไม่เจอข้อมูลใดๆ
            
        except Exception as e:
            print(f"Error checking department data: {e}")
            return True  # ป้องกันการลบเมื่อเกิดข้อผิดพลาด

    def can_delete_campus(self):
        """ตรวจสอบว่าวิทยาเขตสามารถลบได้หรือไม่"""
        campus_name = self.name.get("0", "")
        
        # เช็คข้อมูลระดับ campus ก่อน
        has_campus_data = self._has_related_data(campus_name)
        if has_campus_data:
            return False
        
        # เช็คข้อมูลของทุก department ใน campus นี้
        for dept_key in self.departments.keys():
            has_dept_data = self._has_department_data(campus_name, dept_key)
            if has_dept_data:
                return False  # ถ้า department ไหนมีข้อมูล ก็ลบ campus ไม่ได้
        
        # ถ้าไม่มีข้อมูลใดๆ ทั้งระดับ campus และ department
        return True

    def can_delete_department(self, dept_key):
        """ตรวจสอบว่าหน่วยงานสามารถลบได้หรือไม่"""
        # ตรวจสอบข้อมูลที่เกี่ยวข้อง - เรียกใช้ _has_department_data()
        campus_name = self.name.get("0", "")
        has_data = self._has_department_data(campus_name, dept_key)
        
        # ถ้ามีข้อมูล (has_data = True) → ลบไม่ได้ (return False)
        # ถ้าไม่มีข้อมูล (has_data = False) → ลบได้ (return True)
        return not has_data

    def can_delete_department_by_name(self, campus_name, dept_name):
        """ตรวจสอบว่าหน่วยงานสามารถลบได้หรือไม่ (โดยใช้ชื่อ department)"""
        try:
            campus_id = str(self.id)
            
            # ตรวจสอบจาก User model - หา department_key ที่ตรงกับ dept_name
            from .user_model import User
            # หา department_key ที่มี name ตรงกับ dept_name
            dept_key = None
            for key, name in self.departments.items():
                if name == dept_name:
                    dept_key = key
                    break
            
            if dept_key:
                user_exists = User.objects(campus_id=campus_id, department_key=dept_key).first() is not None
                if user_exists:
                    return False
            
            # ตรวจสอบจาก Material model - เช็คว่ามี Material ที่มีข้อมูลจริงๆ หรือไม่
            from .materail_model import Material
            if dept_key:
                materials = Material.objects(campus=campus_id, department=dept_key)
                
                # เช็คว่ามี Material ที่มีข้อมูลจริงๆ
                for material in materials:
                    has_meaningful_data = (
                        (material.quantity_type and len(material.quantity_type) > 0) or
                        (material.result is not None and material.result != "") or
                        (material.result2 is not None and material.result2 != "")
                    )
                    if has_meaningful_data:
                        return False  # มี Material ที่มีข้อมูลจริงๆ - ห้ามลบ
            
            # ตรวจสอบจาก ReferenceDocument model
            from .file_model import ReferenceDocument
            file_exists = ReferenceDocument.objects(campus=campus_name, department=dept_name).first() is not None
            if file_exists:
                return False
            
            return True  # ไม่เจอข้อมูลใดๆ - ลบได้
            
        except Exception as e:
            print(f"Error checking department data by name: {e}")
            return False  # ป้องกันการลบเมื่อเกิดข้อผิดพลาด

    def add_department(self, department_name):
        """เพิ่มหน่วยงานใหม่ และ copy scope จาก department 'base' อัตโนมัติ"""
        # หา key ใหม่
        existing_keys = list(self.departments.keys())
        new_key = str(max([int(k) for k in existing_keys if k.isdigit()] + [0]) + 1)
        
        # เพิ่มหน่วยงานใหม่
        self.departments[new_key] = department_name
        self.updated_date = datetime.datetime.now()
        self.save()
        
        # Clone scope จาก department 'base' อัตโนมัติ
        try:
            from .scope_model import Scope
            campus_id = str(self.id)
            
            # ลำดับการหา scope เพื่อ clone:
            # 1. หา scope ใน department "base" ของ campus นี้
            # 2. ถ้าไม่มี ให้หา department ที่มี scope มากที่สุด
            # 3. ถ้าไม่มีเลย ให้ copy จาก global base (campus="base")
            
            source_dept = "base"
            cloned_count = 0
            
            # ขั้นตอนที่ 1: ตรวจสอบ department "base" ใน campus นี้
            base_scopes = Scope.objects(campus=campus_id, department="base")
            base_scope_count = base_scopes.count()
            
            if base_scope_count > 0:
                # มี scope ใน local base department
                cloned_count = Scope.clone_for_new_department(campus_id, source_dept, new_key)
            else:
                # ขั้นตอนที่ 2: หาหน่วยงานที่มี scope มากที่สุด
                dept_scope_counts = {}
                for dept_key in self.departments.keys():
                    if dept_key == new_key:  # ข้าม department ใหม่
                        continue
                    dept_scopes = Scope.objects(campus=campus_id, department=dept_key)
                    scope_count = dept_scopes.count()
                    if scope_count > 0:
                        dept_scope_counts[dept_key] = scope_count
                
                if dept_scope_counts:
                    # เลือก department ที่มี scope มากที่สุด
                    source_dept = max(dept_scope_counts.keys(), key=lambda x: dept_scope_counts[x])
                    cloned_count = Scope.clone_for_new_department(campus_id, source_dept, new_key)
                else:
                    # ขั้นตอนที่ 3: Copy จาก global base
                    global_base_scopes = Scope.objects(campus="base", department="base")
                    
                    if global_base_scopes.count() > 0:
                        # Clone จาก global base โดยสร้าง scope ใหม่เอง
                        for scope in global_base_scopes:
                            new_scope = Scope(
                                ghg_scope=scope.ghg_scope,
                                ghg_sup_scope=scope.ghg_sup_scope,
                                ghg_name=scope.ghg_name,
                                ghg_desc=scope.ghg_desc,
                                campus=campus_id,  # ใช้ campus_id ใหม่
                                department=new_key,  # ใช้ department ใหม่
                                head_table=scope.head_table.copy() if scope.head_table else [],
                                create_date=datetime.datetime.now(),
                                update_date=datetime.datetime.now()
                            )
                            new_scope.save()
                            cloned_count += 1
                
        except Exception as e:
            print(f"Error during scope cloning process: {e}")
            import traceback
            traceback.print_exc()
        
        return new_key

    def update_department(self, dept_key, new_name):
        """แก้ไขชื่อหน่วยงาน"""
        if dept_key not in self.departments:
            raise ValueError(f"ไม่พบหน่วยงาน '{dept_key}'")
        
        self.departments[dept_key] = new_name
        self.updated_date = datetime.datetime.now()
        self.save()

    def delete_department(self, dept_key):
        """ลบหน่วยงาน (พร้อมตรวจสอบ)"""
        if not self.can_delete_department(dept_key):
            raise ValueError("ไม่สามารถลบหน่วยงานนี้ได้ เนื่องจากมีข้อมูลที่เกี่ยวข้อง")
        
        del self.departments[dept_key]
        self.updated_date = datetime.datetime.now()
        self.save()

    def update_campus_name(self, new_name, new_description=None):
        """แก้ไขชื่อและคำอธิบายวิทยาเขต"""
        # ตรวจสอบชื่อซ้ำ (ยกเว้นตัวเอง)
        existing = CampusAndDepartment.objects(name__0=new_name, id__ne=self.id).first()
        if existing:
            raise ValueError("ชื่อวิทยาเขตนี้มีอยู่แล้ว")
        
        self.name = {"0": new_name}
        if new_description is not None:
            self.description = new_description
        self.updated_date = datetime.datetime.now()
        self.save()

    @classmethod
    def create_campus(cls, name, description="", default_dept="สำนักงานอธิการบดี"):
        """สร้างวิทยาเขตใหม่"""
        # ตรวจสอบชื่อซ้ำ
        if cls.objects(name__0=name).first():
            raise ValueError("ชื่อวิทยาเขตนี้มีอยู่แล้ว")
        
        campus = cls(
            name={"0": name},
            description=description,
            departments={"1": default_dept}
        )
        campus.save()
        return campus

    def safe_delete(self):
        """ลบวิทยาเขต (พร้อมตรวจสอบ)"""
        if not self.can_delete_campus():
            raise ValueError("ไม่สามารถลบวิทยาเขตนี้ได้ เนื่องจากมีข้อมูลที่เกี่ยวข้อง")
        
        self.delete()

    @staticmethod
    @staticmethod
    def get_campus_name(campus_id):
        """Get campus name from DB by id"""
        campus_obj = CampusAndDepartment.objects(id=campus_id).first()
        if campus_obj:
            return campus_obj.name["0"]  # Assuming name is a dict with key "0" for campus name
        return campus_id

    @staticmethod
    def get_department_name(campus_id, department_key):
        """Get department name by campus id and department key"""
        campus_obj = CampusAndDepartment.objects(id=campus_id).first()
        if campus_obj and department_key in campus_obj.departments:
            return campus_obj.departments[department_key]
        return department_key

    meta = {
            "collection": "campus_and_department",
            "indexes": ["name"],
        }
