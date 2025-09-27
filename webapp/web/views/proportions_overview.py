from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
import datetime
from ...models.materail_model import Material
from ...models.campus_and_department_model import CampusAndDepartment

module = Blueprint("proportions_overview", __name__, url_prefix="/proportions/overview")

CAMPUS_INFO = {
    "hatyai": {"nameTh": "หาดใหญ่", "color": "#10B981"},
    "pattani": {"nameTh": "ปัตตานี", "color": "#3B82F6"},
    "suratthani": {"nameTh": "สุราษฎร์ธานี", "color": "#8B5CF6"},
    "phuket": {"nameTh": "ภูเก็ต", "color": "#F59E0B"},
    "trang": {"nameTh": "ตรัง", "color": "#EF4444"},
}


@module.route("/", methods=["GET"])
@login_required
def overview():
    selected_year = int(request.args.get("year", datetime.datetime.now().year))
    campus_keys = list(CAMPUS_INFO.keys())

    # ดึงข้อมูล Material เฉพาะปีที่เลือก
    materials = Material.objects(
        year=selected_year, result2__ne=None, result2__exists=True
    )

    print("Materials count:", materials.count())

    # สร้าง mapping campus key -> ObjectId
    campus_objs = CampusAndDepartment.objects()
    campus_key_to_id = {}
    for c in campus_objs:
        campus_name_key = c.name.get("0")
        if campus_name_key:
            campus_key_to_id[campus_name_key] = str(c.id)

    # สรุปข้อมูลแต่ละ campus
    campus_summaries = []
    total_all_campuses = sum([m.result2 for m in materials if m.result2]) or 0

    for campus in campus_keys:
        campus_id = campus_key_to_id.get(campus)
        campus_materials = [m for m in materials if str(m.campus) == campus_id]
        print(f"Campus: {campus}, Materials: {len(campus_materials)}")
        departments = set([m.department for m in campus_materials])
        scope1_total = sum(
            [
                m.result2
                for m in campus_materials
                if getattr(m, "scope", None) == 1 and m.result2
            ]
        )
        scope2_total = sum(
            [
                m.result2
                for m in campus_materials
                if getattr(m, "scope", None) == 2 and m.result2
            ]
        )
        scope3_total = sum(
            [
                m.result2
                for m in campus_materials
                if getattr(m, "scope", None) == 3 and m.result2
            ]
        )
        total_emissions = sum([m.result2 for m in campus_materials if m.result2])
        if total_all_campuses > 0:
            percentage_of_total = total_emissions / total_all_campuses * 100
        else:
            percentage_of_total = 0

        campus_summaries.append(
            {
                "campus": campus,
                "campusNameTh": CAMPUS_INFO[campus]["nameTh"],
                "departments": len(departments),
                "scope1Total": scope1_total,
                "scope2Total": scope2_total,
                "scope3Total": scope3_total,
                "totalEmissions": total_emissions,
                "percentageOfTotal": percentage_of_total,
                "color": CAMPUS_INFO[campus]["color"],
            }
        )

    campus_summaries.sort(key=lambda x: x["totalEmissions"], reverse=True)

    overall_stats = {
        "total": sum([c["totalEmissions"] for c in campus_summaries]),
        "totalScope1": sum([c["scope1Total"] for c in campus_summaries]),
        "totalScope2": sum([c["scope2Total"] for c in campus_summaries]),
        "totalScope3": sum([c["scope3Total"] for c in campus_summaries]),
        "totalDepartments": sum([c["departments"] for c in campus_summaries]),
    }

    years = Material.objects(result2__ne=None, result2__exists=True).distinct("year")
    years = sorted([y for y in years if isinstance(y, int)], reverse=True)

    return render_template(
        "proportions-overview/overview.html",
        campus_summaries=campus_summaries,
        overall_stats=overall_stats,
        selected_year=selected_year,
        campus_info=CAMPUS_INFO,
        years=years,
    )
