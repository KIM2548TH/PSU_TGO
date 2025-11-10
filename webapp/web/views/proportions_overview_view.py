from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from ..utils.acl import permissions_required_all
import datetime
from ...models.materail_model import Material
from ...models.campus_and_department_model import CampusAndDepartment

module = Blueprint("proportions_overview", __name__, url_prefix="/proportions/overview")

def generate_campus_colors(count):
    """สร้างสีสำหรับ campus แบบ dynamic"""
    colors = [
        "#10B981",  # Green
        "#3B82F6",  # Blue
        "#8B5CF6",  # Purple
        "#F59E0B",  # Amber
        "#EF4444",  # Red
        "#06B6D4",  # Cyan
        "#84CC16",  # Lime
        "#F97316",  # Orange
        "#EC4899",  # Pink
        "#6366F1",  # Indigo
        "#14B8A6",  # Teal
        "#A855F7",  # Violet
    ]
    
    # ถ้าจำนวน campus มากกว่าสีที่มี ให้ repeat
    while len(colors) < count:
        colors.extend(colors)
    
    return colors[:count]

@module.route("/", methods=["GET"])
@login_required
@permissions_required_all(["เข้าถึงหน้าภาพรวมสัดส่วนการปล่อย"])
def overview():
    selected_year = int(request.args.get("year", datetime.datetime.now().year))
    
    # ดึงข้อมูล Material เฉพาะปีที่เลือกก่อน
    materials = Material.objects(
        year=selected_year, result2__ne=None, result2__exists=True
    )

    
    # ดึง campus IDs ที่มีข้อมูล Material จริงๆ
    campus_ids_with_data = list(set([str(m.campus) for m in materials]))
    
    
    # ดึงข้อมูล Campus เฉพาะที่มีข้อมูล Material + campus ทั้งหมดที่มีอยู่
    all_campus_objs = CampusAndDepartment.objects()
    campus_objs_with_data = [c for c in all_campus_objs if str(c.id) in campus_ids_with_data]
    
    
    
    
    # ถ้าไม่มี campus ที่ตรงกัน ให้ใช้ข้อมูลจาก Material โดยตรง
    campus_info = {}
    
    if campus_objs_with_data:
        # กรณีมี campus ที่ตรงกัน
        for campus_obj in campus_objs_with_data:
            campus_id = str(campus_obj.id)
            campus_name = campus_obj.name.get("0", "ไม่ระบุชื่อ")
            campus_info[campus_id] = {
                "name": campus_name,
                "nameTh": campus_name,
                "departments_count": len(campus_obj.departments)
            }
            
    else:
        # กรณี campus ID ไม่ตรงกัน - สร้างข้อมูล campus จาก Material
        
        for campus_id in campus_ids_with_data:
            # หาชื่อ campus จาก Material หรือใช้ ID แทน
            campus_materials = [m for m in materials if str(m.campus) == campus_id]
            departments = set([m.department for m in campus_materials])
            
            # ลองหาชื่อ campus จาก CampusAndDepartment โดยใช้ name lookup
            campus_name = campus_id
            for campus_obj in all_campus_objs:
                if campus_obj.name.get("0", "") == campus_id:
                    campus_name = campus_obj.name.get("0", campus_id)
                    break
            
            campus_info[campus_id] = {
                "name": campus_name,
                "nameTh": campus_name,
                "departments_count": len(departments)
            }
            
    
    # เพิ่ม campus ที่ไม่มีข้อมูลแต่อยู่ในระบบ
    for campus_obj in all_campus_objs:
        campus_id = str(campus_obj.id)
        if campus_id not in campus_info:
            campus_name = campus_obj.name.get("0", "ไม่ระบุชื่อ")
            campus_info[campus_id] = {
                "name": campus_name,
                "nameTh": campus_name,
                "departments_count": len(campus_obj.departments)
            }
    
    # สร้างสีสำหรับแต่ละ campus
    colors = generate_campus_colors(len(campus_info))
    campus_ids = list(campus_info.keys())
    
    for i, campus_id in enumerate(campus_ids):
        campus_info[campus_id]["color"] = colors[i]
    
    # สรุปข้อมูลแต่ละ campus
    campus_summaries = []
    total_all_campuses = sum([float(m.result2) for m in materials if m.result2]) or 0
    

    for campus_id, info in campus_info.items():
        # กรองข้อมูล Material ของแต่ละ campus
        campus_materials = [m for m in materials if str(m.campus) == campus_id]
        
        # นับจำนวน department ที่มีข้อมูล Material จริงๆ
        departments_with_data = set([m.department for m in campus_materials])
        
        scope1_total = sum([
            float(m.result2) for m in campus_materials 
            if getattr(m, "scope", None) == 1 and m.result2
        ])
        scope2_total = sum([
            float(m.result2) for m in campus_materials 
            if getattr(m, "scope", None) == 2 and m.result2
        ])
        scope3_total = sum([
            float(m.result2) for m in campus_materials 
            if getattr(m, "scope", None) == 3 and m.result2
        ])
        
        total_emissions = sum([float(m.result2) for m in campus_materials if m.result2])
        
        if total_all_campuses > 0:
            percentage_of_total = total_emissions / total_all_campuses * 100
        else:
            percentage_of_total = 0

        campus_summaries.append({
            "campus_id": campus_id,
            "campus": info["name"],
            "campusNameTh": info["nameTh"],
            "departments": len(departments_with_data),  # นับจาก department ที่มีข้อมูลจริง
            "scope1Total": scope1_total,
            "scope2Total": scope2_total,
            "scope3Total": scope3_total,
            "totalEmissions": total_emissions,
            "percentageOfTotal": percentage_of_total,
            "color": info["color"],
        })

    # เรียงลำดับตามการปล่อยรวม (มากไปน้อย)
    campus_summaries.sort(key=lambda x: x["totalEmissions"], reverse=True)

    overall_stats = {
        "total": sum([c["totalEmissions"] for c in campus_summaries]),
        "totalScope1": sum([c["scope1Total"] for c in campus_summaries]),
        "totalScope2": sum([c["scope2Total"] for c in campus_summaries]),
        "totalScope3": sum([c["scope3Total"] for c in campus_summaries]),
        "totalDepartments": sum([c["departments"] for c in campus_summaries]),
    }

    # ดึงรายการปีที่มีข้อมูล
    years = Material.objects(result2__ne=None, result2__exists=True).distinct("year")
    years = sorted([y for y in years if isinstance(y, int)], reverse=True)

    return render_template(
        "proportions-overview/overview.html",
        campus_summaries=campus_summaries,
        overall_stats=overall_stats,
        selected_year=selected_year,
        campus_info=campus_info,
        years=years,
    )
