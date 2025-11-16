import mongoengine as me
import datetime


class InputType(me.EmbeddedDocument):
    field = me.StringField(required=True)  # ชื่อฟิลด์ เช่น "n"
    label = me.StringField(required=True)  # คำอธิบาย เช่น "ไนโตรเจน (N)"
    input_type = me.StringField(
        required=True, choices=["number", "text", "select"]
    )  # ประเภทอินพุต เช่น "number"
    unit = me.StringField(required=False, default="")  # หน่วย เช่น "kg"

    @staticmethod
    def create_input(field, label, input_type, unit=""):
        """
        สร้าง InputType ใหม่
        """
        return InputType(field=field, label=label, input_type=input_type, unit=unit)


class FormAndFormula(me.Document):
    ghg_scope = me.IntField(required=True, choices=[1, 2, 3])
    ghg_sup_scope = me.IntField(required=True)
    desc_form = me.StringField(required=True)
    desc_formula = me.StringField(required=False, default="")
    desc_formula2 = me.StringField(required=False, default="")
    material_name = me.StringField(required=True)
    
    # ระบบลิงก์
    is_linked = me.BooleanField(default=False)  # เป็นฟอร์มที่ลิงก์หรือไม่
    linked_material_name = me.StringField(required=False)  # ชื่อ material ที่ต้องการลิงก์
    
    input_types = me.EmbeddedDocumentListField(InputType)
    variables = me.ListField(me.StringField(), required=False, default=[])
    formula = me.StringField(required=False, default="")
    formula2 = me.StringField(required=False, default="")
    
    # Gas calculation formulas (7 types)
    formula_co2 = me.StringField(required=False, default="")
    formula_ch4 = me.StringField(required=False, default="")
    formula_n2o = me.StringField(required=False, default="")
    formula_hfcs = me.StringField(required=False, default="")
    formula_pfcs = me.StringField(required=False, default="")
    formula_sf6 = me.StringField(required=False, default="")
    formula_nf3 = me.StringField(required=False, default="")
    
    create_date = me.DateTimeField(default=datetime.datetime.now)
    update_date = me.DateTimeField(default=datetime.datetime.now)

    def save_form(self):
        self.update_date = datetime.datetime.now()
        self.save()

    def setup_linked_form(self, linked_material_name):
        """
        ตั้งค่าฟอร์มให้เป็นแบบลิงก์และสร้าง auto input_types
        """
        self.is_linked = True
        self.linked_material_name = linked_material_name
        
        # สร้าง buffer field อัตโนมัติ
        auto_field = InputType.create_input(
            field="buffer_data",
            label="ข้อมูลจากระบบ (อัตโนมัติ)",
            input_type="number",
            unit="unit"
        )
        self.input_types = [auto_field]
        self.variables = ["buffer_data"]

    def get_linked_data(self, year, month, campus, department):
        """
        ดึงข้อมูลจาก Material ที่ลิงก์
        """
        if not self.is_linked or not self.linked_material_name:
            return None
            
        from webapp.models.materail_model import Material
        
        # ดึงข้อมูล Material ที่ต้องการ
        materials = Material.objects(
            name=self.linked_material_name,
            year=year,
            month=month,
            campus=campus,
            department=department
        )
        
        total_value = 0
        for material in materials:
            if material.result is not None:
                total_value += float(material.result)
                
        return total_value

    def calculate_linked_result(self, year, month, campus, department):
        """
        คำนวณผลลัพธ์จากข้อมูลที่ลิงก์
        """
        if not self.is_linked:
            return None
            
        linked_data = self.get_linked_data(year, month, campus, department)
        if linked_data is None:
            return None
            
        # แทนค่าในสูตร
        try:
            # สร้าง variables dict สำหรับคำนวณ
            variables_dict = {"buffer_data": linked_data}
            
            # แทนที่ตัวแปรในสูตร
            formula_to_execute = self.formula
            for var_name, value in variables_dict.items():
                formula_to_execute = formula_to_execute.replace(var_name, str(value))
            
            # คำนวณผลลัพธ์
            result = eval(formula_to_execute)
            return float(result)
            
        except Exception as e:
            print(f"Error calculating linked result: {e}")
            return None

    meta = {
        "collection": "form_and_formula",
        "indexes": ["material_name", "is_linked", "linked_material_name"],
    }


# from webapp.models.form_and_formula_model import FormAndFormula, InputType

# # สร้างฟอร์มใหม่
# form = FormAndFormula(
#     name="สูตรคำนวณคาร์บอนฟุตพริ้นท์ปุ๋ย",
#     desc_form="ฟอร์มคำนวณคาร์บอนฟุตพริ้นท์จาก NPK",
#     desc_formula="สูตรนี้จะรวมคาร์บอนฟุตพริ้นท์ของ N, P, และ K โดยใช้สัดส่วนที่กำหนด",
#     variables=["n", "p", "k"],
#     formula="n * 1.2 + p * 1.1 + k * 0.9"
# )

# # เพิ่ม InputType ลงในฟอร์ม
# form.add_input_type(InputType.create_input(field="n", label="ไนโตรเจน (N)", input_type="number", unit="kg"))
# form.add_input_type(InputType.create_input(field="p", label="ฟอสฟอรัส (P)", input_type="number", unit="kg"))
# form.add_input_type(InputType.create_input(field="k", label="โพแทสเซียม (K)", input_type="number", unit="kg"))

# # บันทึกฟอร์มลงในฐานข้อมูล
# form.save_form()
