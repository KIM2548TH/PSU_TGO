"""
Gas Calculation Module
สำหรับคำนวณผลลัพธ์ก๊าซ 7 ชนิดจากสูตรที่กำหนด
"""

def calculate_gas_results(material, form_obj=None):
    """
    คำนวณผลลัพธ์ก๊าซ 7 ชนิดจาก Material และ Form
    
    Args:
        material: Material object
        form_obj: FormAndFormula object (optional)
    
    Returns:
        dict: ผลลัพธ์การคำนวณก๊าซทั้ง 7 ชนิด
    """
    if not form_obj:
        from ...models import FormAndFormula
        form_obj = FormAndFormula.objects(
            material_name=material.name,
            ghg_scope=material.scope,
            ghg_sup_scope=material.sub_scope
        ).first()
    
    if not form_obj:
        return {}
    
    # สร้างตัวแปรสำหรับการคำนวณ
    variables = _build_variables_dict(material)
    
    # คำนวณก๊าซแต่ละชนิด
    gas_results = {}
    
    gas_formulas = {
        'co2': getattr(form_obj, 'formula_co2', ''),
        'ch4': getattr(form_obj, 'formula_ch4', ''),
        'n2o': getattr(form_obj, 'formula_n2o', ''),
        'hfcs': getattr(form_obj, 'formula_hfcs', ''),
        'pfcs': getattr(form_obj, 'formula_pfcs', ''),
        'sf6': getattr(form_obj, 'formula_sf6', ''),
        'nf3': getattr(form_obj, 'formula_nf3', '')
    }
    
    for gas_type, formula in gas_formulas.items():
        if formula and formula.strip():
            try:
                result = _evaluate_gas_formula(formula, variables)
                gas_results[f'result_{gas_type}'] = result
            except Exception as e:
                print(f"Error calculating {gas_type}: {e}")
                gas_results[f'result_{gas_type}'] = None
        else:
            gas_results[f'result_{gas_type}'] = None
    
    # อัปเดตค่าใน Material object
    for field, value in gas_results.items():
        setattr(material, field, value)
    
    return gas_results


def _build_variables_dict(material):
    """
    สร้าง dictionary ของตัวแปรสำหรับการคำนวณ
    
    Args:
        material: Material object
    
    Returns:
        dict: ตัวแปรทั้งหมดที่ใช้ได้ในสูตร
    """
    variables = {}
    
    # เพิ่มตัวแปรจาก quantity_type
    if hasattr(material, 'quantity_type') and material.quantity_type:
        for qty in material.quantity_type:
            variables[qty.field] = qty.amount if qty.amount is not None else 0
    
    # เพิ่มตัวแปรพื้นฐาน
    variables['result'] = material.result if material.result is not None else 0
    variables['result2'] = material.result2 if material.result2 is not None else 0
    
    # เพิ่มตัวแปรทั่วไปที่ใช้บ่อย
    common_variables = {
        'diesel': 0,
        'gasoline': 0,
        'electricity': 0,
        'water': 0,
        'waste': 0,
        'coal': 0,
        'natural_gas': 0,
        'lpg': 0,
        'propane': 0,
        'butane': 0
    }
    
    # พยายามหาค่าจาก quantity_type ก่อน
    for var_name in common_variables:
        if var_name in variables:
            common_variables[var_name] = variables[var_name]
    
    variables.update(common_variables)
    
    return variables


def _evaluate_gas_formula(formula, variables):
    """
    ประเมินสูตรคำนวณก๊าซ
    
    Args:
        formula (str): สูตรคำนวณ
        variables (dict): ค่าตัวแปร
    
    Returns:
        float: ผลลัพธ์การคำนวณ
    """
    if not formula or not formula.strip():
        return None
    
    try:
        # แทนที่ตัวแปรในสูตร
        formula_to_execute = formula.strip()
        
        # แทนที่ตัวแปรที่เป็นตัวอักษรภาษาไทย
        thai_var_mapping = {
            'ดีเซล': 'diesel',
            'เบนซิน': 'gasoline',
            'ไฟฟ้า': 'electricity',
            'น้ำ': 'water',
            'ขยะ': 'waste',
            'ถ่าน': 'coal',
            'ก๊าซธรรมชาติ': 'natural_gas',
            'แก๊ส': 'natural_gas'
        }
        
        for thai_var, eng_var in thai_var_mapping.items():
            formula_to_execute = formula_to_execute.replace(thai_var, str(variables.get(eng_var, 0)))
        
        # แทนที่ตัวแปรภาษาอังกฤษ
        for var_name, value in variables.items():
            if value is not None:
                formula_to_execute = formula_to_execute.replace(var_name, str(value))
            else:
                formula_to_execute = formula_to_execute.replace(var_name, '0')
        
        # คำนวณผลลัพธ์
        result = eval(formula_to_execute)
        
        # ตรวจสอบว่าเป็นตัวเลข
        if isinstance(result, (int, float)):
            return float(result)
        else:
            return None
            
    except Exception as e:
        print(f"Error evaluating formula '{formula}': {e}")
        return None


def get_gas_summary(material):
    """
    สรุปผลลัพธ์ก๊าซทั้งหมดจาก Material
    
    Args:
        material: Material object
    
    Returns:
        dict: สรุปผลลัพธ์ก๊าซแต่ละชนิด
    """
    gas_fields = [
        ('result_co2', 'CO₂', 'kg'),
        ('result_ch4', 'CH₄', 'kg'),
        ('result_n2o', 'N₂O', 'kg'),
        ('result_hfcs', 'HFCs', 'kg'),
        ('result_pfcs', 'PFCs', 'kg'),
        ('result_sf6', 'SF₆', 'kg'),
        ('result_nf3', 'NF₃', 'kg')
    ]
    
    summary = {}
    total_co2e = 0
    
    for field, name, unit in gas_fields:
        value = getattr(material, field, None)
        if value is not None:
            summary[field] = {
                'name': name,
                'value': float(value),
                'unit': unit,
                'has_value': True
            }
            # คำนวณ CO2e (ใช้ GWP 100 ปี)
            co2e = _calculate_co2e(name, float(value))
            total_co2e += co2e
        else:
            summary[field] = {
                'name': name,
                'value': None,
                'unit': unit,
                'has_value': False
            }
    
    summary['total_co2e'] = total_co2e
    
    return summary


def _calculate_co2e(gas_name, value):
    """
    คำนวณค่า CO2 equivalent โดยใช้ Global Warming Potential (GWP)
    
    Args:
        gas_name (str): ชื่อก๊าซ
        value (float): ค่าของก๊าซ
    
    Returns:
        float: ค่า CO2e
    """
    # GWP 100 ปี ตาม IPCC AR5
    gwp_factors = {
        'CO₂': 1.0,
        'CH₄': 28.0,
        'N₂O': 265.0,
        'HFCs': 100.0,  # ค่าเฉลี่ย (ขึ้นอยู่กับชนิด)
        'PFCs': 6500.0,  # ค่าเฉลี่ย (ขึ้นอยู่กับชนิด)
        'SF₆': 23900.0,
        'NF₃': 16100.0
    }
    
    gwp = gwp_factors.get(gas_name, 1.0)
    return value * gwp


def validate_gas_formula(formula, available_variables):
    """
    ตรวจสอบความถูกต้องของสูตรก๊าซ
    
    Args:
        formula (str): สูตรที่ต้องการตรวจสอบ
        available_variables (list): รายชื่อตัวแปรที่ใช้ได้
    
    Returns:
        dict: ผลการตรวจสอบ
    """
    if not formula or not formula.strip():
        return {
            'valid': True,
            'message': 'ไม่ได้กำหนดสูตร',
            'used_variables': []
        }
    
    try:
        # หาตัวแปรที่ใช้ในสูตร
        import re
        variables_in_formula = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', formula)
        
        # ตรวจสอบว่าตัวแปรที่ใช้อยู่ในรายการที่อนุญาตหรือไม่
        invalid_variables = []
        used_variables = []
        
        for var in variables_in_formula:
            if var not in available_variables and var not in ['result', 'result2']:
                invalid_variables.append(var)
            else:
                used_variables.append(var)
        
        # ตรวจสอบ syntax โดยลองคำนวณกับค่าตัวอย่าง
        sample_values = {var: 1 for var in used_variables}
        sample_values.update({
            'diesel': 100, 'gasoline': 50, 'electricity': 1000,
            'water': 500, 'waste': 200, 'result': 100, 'result2': 0.1
        })
        
        test_result = _evaluate_gas_formula(formula, sample_values)
        
        return {
            'valid': len(invalid_variables) == 0 and test_result is not None,
            'message': f'ตัวแปรที่ใช้ไม่ได้: {", ".join(invalid_variables)}' if invalid_variables else 'สูตรถูกต้อง',
            'used_variables': list(set(used_variables)),
            'invalid_variables': invalid_variables,
            'test_result': test_result
        }
        
    except Exception as e:
        return {
            'valid': False,
            'message': f'สูตรผิดพลาด: {str(e)}',
            'used_variables': [],
            'invalid_variables': []
        }


def get_gas_formula_suggestions(material_name):
    """
    แนะนำสูตรก๊าซสำหรับวัสดุชนิดต่างๆ
    
    Args:
        material_name (str): ชื่อวัสดุ
    
    Returns:
        dict: คำแนะนำสูตรสำหรับก๊าซแต่ละชนิด
    """
    # คำแนะนำสูตรพื้นฐานสำหรับวัสดุทั่วไป
    base_suggestions = {
        'diesel': {
            'co2': 'result * 0.8',
            'ch4': 'result * 0.05',
            'n2o': 'result * 0.02',
            'hfcs': 'result * 0.001',
            'pfcs': 'result * 0.0005',
            'sf6': 'result * 0.0001',
            'nf3': 'result * 0.00005'
        },
        'gasoline': {
            'co2': 'result * 0.75',
            'ch4': 'result * 0.04',
            'n2o': 'result * 0.015',
            'hfcs': 'result * 0.0008',
            'pfcs': 'result * 0.0004',
            'sf6': 'result * 0.00008',
            'nf3': 'result * 0.00004'
        },
        'electricity': {
            'co2': 'result * 0.6',
            'ch4': 'result * 0.01',
            'n2o': 'result * 0.005',
            'hfcs': 'result * 0.0002',
            'pfcs': 'result * 0.0001',
            'sf6': 'result * 0.00002',
            'nf3': 'result * 0.00001'
        }
    }
    
    # ค้นหาคำแนะนำที่ตรงกับชื่อวัสดุ
    material_lower = material_name.lower()
    
    for key, suggestions in base_suggestions.items():
        if key in material_lower:
            return suggestions
    
    # คืนค่าคำแนะนำทั่วไปถ้าไม่ตรงกับกรณีพิเศษ
    return base_suggestions['diesel']
