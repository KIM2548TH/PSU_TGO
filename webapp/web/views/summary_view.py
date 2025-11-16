from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required, current_user
from ...models import Scope, CampusAndDepartment
from ...models.materail_model import Material, QuantityType
from datetime import datetime, timedelta
from bson import ObjectId
from ..utils.acl import permissions_required_all
import urllib.parse
import json
import base64

module = Blueprint("summary", __name__, url_prefix="/summary")


@module.route("/", methods=["GET"])
@login_required
@permissions_required_all(["เข้าถึงหน้าสรุปผล"])
def summary():
    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(user.campus_id, user.department_key)
    return render_template("/summary/summary.html", user=user)


@module.route("/scopes", methods=["GET"])
@login_required
def get_scopes():
    """HTMX endpoint สำหรับ load scope dropdown"""
    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(user.campus_id, user.department_key)

    all_scopes = Scope.objects(campus=user.campus_id, department=user.department_key)
    seen = set()
    unique_scopes = [
        s for s in all_scopes if not (s.ghg_scope in seen or seen.add(s.ghg_scope))
    ]

    return render_template(
        "/summary/partials/scope_dropdown.html", scopes=unique_scopes
    )


@module.route("/sub-scopes", methods=["POST"])
@login_required
def get_sub_scopes():
    """HTMX endpoint สำหรับ load sub scope dropdown ตาม scope ที่เลือก"""
    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(user.campus_id, user.department_key)
    
    selected_scopes = request.form.getlist("selected_scopes")
    current_selected_sub_scopes = request.form.getlist("selected_sub_scopes")

    if not selected_scopes:
        sub_scopes = Scope.objects(
            campus=user.campus_id,
            department=user.department_key,
        ).order_by("ghg_scope", "ghg_sup_scope")
    else:
        sub_scopes = Scope.objects(
            campus=user.campus_id,
            department=user.department_key,
            ghg_scope__in=[int(scope) for scope in selected_scopes],
        ).order_by("ghg_scope", "ghg_sup_scope")

    return render_template(
        "/summary/partials/sub_scope_dropdown.html",
        sub_scopes=sub_scopes,
        current_selected_sub_scopes=current_selected_sub_scopes,
    )


@module.route("/api/materials", methods=["GET"])
@login_required
def get_materials():
    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(user.campus_id, user.department_key)
    
    sub_scopes = request.args.getlist("sub_scopes[]")
    time_period = request.args.get("time_period", "week")

    if not sub_scopes:
        return jsonify(
            {
                "total_emissions": 0,
                "daily_average": 0,
                "materials_count": 0,
                "daily_data": {},
                "category_data": {},
            }
        )

    today = datetime.now()
    days = {"week": 7, "month": 30, "year": 365}
    start_date = today - timedelta(days=days[time_period])

    sub_scope_ids = [int(s) for s in sub_scopes]
    materials = Material.objects(
        campus=user.campus_id,
        department=user.department_key,
        sub_scope__in=sub_scope_ids,
        create_date__gte=start_date,
    )

    total_emissions = sum(m.result2 or 0 for m in materials)
    daily_average = total_emissions / days[time_period]

    daily_data = {}
    for material in materials:
        date_key = f"{material.year}-{material.month:02d}-{material.day:02d}"
        daily_data[date_key] = daily_data.get(date_key, 0) + (material.result2 or 0)

    category_data = {}
    for sub_scope_id in sub_scope_ids:
        scope = Scope.objects(
            campus=user.campus_id, department=user.department_key, ghg_sup_scope=sub_scope_id
        ).first()

        if scope:
            scope_name = f"Scope {scope.ghg_scope}"
            emissions = sum(
                m.result2 or 0 for m in materials if m.sub_scope == sub_scope_id
            )
            category_data[scope_name] = category_data.get(scope_name, 0) + emissions

    return jsonify(
        {
            "total_emissions": round(total_emissions, 2),
            "daily_average": round(daily_average, 2),
            "daily_data": daily_data,
            "category_data": category_data,
            "materials_count": materials.count(),
        }
    )


@module.route("/clear-stats", methods=["POST"])
@login_required
def clear_stats():
    """HTMX endpoint สำหรับ clear stats เมื่อ scope เปลี่ยน"""
    return """
    <div class="text-center text-gray-500 p-8 bg-white rounded-lg shadow-sm">
        <i data-feather="bar-chart-2" class="w-8 h-8 sm:w-12 sm:h-12 mx-auto mb-4 text-gray-300"></i>
        <p class="text-base sm:text-lg">Select Sub Scopes to view statistics</p>
    </div>
    <script>
        if (typeof feather !== 'undefined') {
            feather.replace();
        }
    </script>
    """


@module.route("/clear-charts", methods=["POST"])
@login_required
def clear_charts():
    """HTMX endpoint สำหรับ clear charts เมื่อ scope เปลี่ยน"""
    return """
    <div class="text-center text-gray-500 p-8 bg-white rounded-lg shadow-sm">
        <i data-feather="pie-chart" class="w-8 h-8 sm:w-12 sm:h-12 mx-auto mb-4 text-gray-300"></i>
        <p class="text-base sm:text-lg">Select Sub Scopes to view charts</p>
    </div>
    <script>
        if (typeof feather !== 'undefined') {
            feather.replace();
        }
    </script>
    """


@module.route("/stats", methods=["POST"])
@login_required
def get_stats():
    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(user.campus_id, user.department_key)

    form_selected_scopes = request.form.getlist("selected_scopes")
    form_selected_sub_scopes = request.form.getlist("selected_sub_scopes")
    if form_selected_scopes:
        session['selected_scopes'] = form_selected_scopes
    if form_selected_sub_scopes:
        session['selected_sub_scopes'] = form_selected_sub_scopes

    selected_scopes = form_selected_scopes or session.get('selected_scopes', [])
    selected_sub_scopes = form_selected_sub_scopes or session.get('selected_sub_scopes', [])
    time_period = request.form.get("time_period", "week")
    selected_year = request.form.get("selected_year", datetime.now().year)

    if not selected_sub_scopes:
        return '''
    <div id="stats-container" class="mb-6">
      <div class="text-center text-gray-500 p-8 bg-white rounded-lg shadow-sm">
        <i data-feather="bar-chart-2" class="w-8 h-8 sm:w-12 sm:h-12 mx-auto mb-4 text-gray-300"></i>
        <p class="text-base sm:text-lg">Select Sub Scopes to view statistics</p>
      </div>
    </div>
    <script>if (window.feather) feather.replace();</script>
    '''

    scope_object_ids = [ObjectId(x) for x in selected_sub_scopes]
    all_selected_sub_scopes = Scope.objects(
        id__in=scope_object_ids,
        campus=user.campus_id,
        department=user.department_key
    )

    if selected_scopes:
        valid_sub_scopes = [
            s for s in all_selected_sub_scopes
            if s.ghg_scope in [int(v) for v in selected_scopes]
        ]
    else:
        valid_sub_scopes = list(all_selected_sub_scopes)

    valid_ids = [str(s.id) for s in valid_sub_scopes]

    if not valid_ids:
        return '''
    <div id="stats-container" class="mb-6">
      <div class="text-center text-gray-500 p-8 bg-white rounded-lg shadow-sm">
        <i data-feather="bar-chart-2" class="w-8 h-8 sm:w-12 sm:h-12 mx-auto mb-4 text-gray-300"></i>
        <p class="text-base sm:text-lg">Select Scopes to view data</p>
      </div>
    </div>
    <script>if (window.feather) feather.replace();</script>
    '''

    data = calculate_emissions_data(user, valid_ids, time_period, selected_year)
    scopes = Scope.objects(campus=user.campus_id, department=user.department_key)
    unique_scopes = {s.ghg_scope: s for s in scopes}.values()

    # ใช้ไฟล์เดิม (start_partial.html) เพื่อคืน layout การ์ดเดิม + Top Sub Scopes toggle
    return render_template(
        "/summary/start_partial.html",
        data=data,
        time_period=time_period,
        scopes=unique_scopes,
        selected_year=int(selected_year),
    )


@module.route("/charts", methods=["POST"])
@login_required
def get_charts():
    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(user.campus_id, user.department_key)

    form_selected_scopes = request.form.getlist("selected_scopes")
    form_selected_sub_scopes = request.form.getlist("selected_sub_scopes")
    if form_selected_scopes:
        session['selected_scopes'] = form_selected_scopes
    if form_selected_sub_scopes:
        session['selected_sub_scopes'] = form_selected_sub_scopes

    selected_scopes = form_selected_scopes or session.get('selected_scopes', [])
    selected_sub_scopes = form_selected_sub_scopes or session.get('selected_sub_scopes', [])
    time_period = request.form.get("time_period", "week")
    selected_year = int(request.form.get("selected_year", datetime.now().year))

    if not selected_sub_scopes:
        return '''
    <div id="charts-container">
      <div class="text-center text-gray-500 p-8 bg-white rounded-lg shadow-sm">
        <i data-feather="pie-chart" class="w-8 h-8 sm:w-12 sm:h-12 mx-auto mb-4 text-gray-300"></i>
        <p class="text-base sm:text-lg">Select Sub Scopes to view charts</p>
      </div>
    </div>
    <script>if (window.feather) feather.replace();</script>
    '''

    scope_object_ids = [ObjectId(x) for x in selected_sub_scopes]
    all_selected_sub_scopes = Scope.objects(
        id__in=scope_object_ids,
        campus=user.campus_id,
        department=user.department_key
    )

    if selected_scopes:
        valid_sub_scopes = [
            s for s in all_selected_sub_scopes
            if s.ghg_scope in [int(v) for v in selected_scopes]
        ]
    else:
        valid_sub_scopes = list(all_selected_sub_scopes)

    valid_ids = [str(s.id) for s in valid_sub_scopes]

    if not valid_ids:
        return '''
    <div id="charts-container">
      <div class="text-center text-gray-500 p-8 bg-white rounded-lg shadow-sm">
        <i data-feather="pie-chart" class="w-8 h-8 sm:w-12 sm:h-12 mx-auto mb-4 text-gray-300"></i>
        <p class="text-base sm:text-lg">Select Scopes to view charts</p>
      </div>
    </div>
    <script>if (window.feather) feather.replace();</script>
    '''

    current_year_data = calculate_emissions_data(user, valid_ids, time_period, selected_year)
    previous_year_data = calculate_emissions_data(user, valid_ids, time_period, selected_year - 1)

    return render_template(
        "/summary/charts_partial.html",
        data=current_year_data,
        previous_year_data=previous_year_data,
        selected_year=selected_year,
    )


def calculate_emissions_data(user, sub_scopes, time_period, selected_year=None):
    """คำนวณข้อมูล emissions"""
    if not selected_year:
        selected_year = datetime.now().year

    scope_object_ids = [ObjectId(scope_id) for scope_id in sub_scopes]

    scopes = Scope.objects(
        id__in=scope_object_ids, campus=user.campus_id, department=user.department_key
    )

    scope_pairs = list(set([(scope.ghg_scope, scope.ghg_sup_scope) for scope in scopes]))
    
    materials_list = []
    for ghg_scope, ghg_sup_scope in scope_pairs:
        materials_for_scope = Material.objects(
            campus=user.campus_id,
            department=user.department_key,
            scope=ghg_scope,
            sub_scope=ghg_sup_scope,
            year=int(selected_year),
        )
        materials_list.extend(materials_for_scope)

    unique_materials = {}
    for material in materials_list:
        material_id = str(material.id)
        if material_id not in unique_materials:
            unique_materials[material_id] = material
    
    materials_list = list(unique_materials.values())

    last_year_materials_list = []
    for ghg_scope, ghg_sup_scope in scope_pairs:
        last_year_materials_for_scope = Material.objects(
            campus=user.campus_id,
            department=user.department_key,
            scope=ghg_scope,
            sub_scope=ghg_sup_scope,
            year=int(selected_year) - 1,
        )
        last_year_materials_list.extend(last_year_materials_for_scope)

    unique_last_year_materials = {}
    for material in last_year_materials_list:
        material_id = str(material.id)
        if material_id not in unique_last_year_materials:
            unique_last_year_materials[material_id] = material
    
    last_year_materials_list = list(unique_last_year_materials.values())

    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]

    daily_data = {month: 0 for month in month_names}

    for material in materials_list:
        if material.month and 1 <= material.month <= 12:
            month_name = month_names[material.month - 1]
            emission_value = material.result2 or 0
            daily_data[month_name] += emission_value

    category_data = {}
    scope_data = {}
    
    for ghg_scope, ghg_sup_scope in scope_pairs:
        scope_name = f"Scope {ghg_scope}"
        
        scope_materials = [
            m for m in materials_list 
            if m.scope == ghg_scope and m.sub_scope == ghg_sup_scope
        ]
        emissions = sum(m.result2 or 0 for m in scope_materials)
        
        category_data[scope_name] = category_data.get(scope_name, 0) + emissions

        scope_key = f"Scope {ghg_scope}.{ghg_sup_scope}"
        
        scope_object = next((s for s in scopes if s.ghg_scope == ghg_scope and s.ghg_sup_scope == ghg_sup_scope), None)
        
        scope_data[scope_key] = {
            "ghg_scope": ghg_scope,
            "ghg_sup_scope": ghg_sup_scope,
            "emissions": emissions,
            "scope_object": scope_object,
            "ghg_name": scope_object.ghg_name if scope_object else f"Scope {ghg_scope}.{ghg_sup_scope}",
        }

    current_year_total = sum(m.result2 or 0 for m in materials_list)
    last_year_total = sum(m.result2 or 0 for m in last_year_materials_list)

    if last_year_total > 0:
        year_change_percent = (
            (current_year_total - last_year_total) / last_year_total
        ) * 100
    else:
        year_change_percent = 100 if current_year_total > 0 else 0

    if time_period == "Day":
        daily_average = current_year_total / 365
        average_label = "Per Day"
    elif time_period == "week":
        daily_average = current_year_total / 52
        average_label = "Per Week"
    elif time_period == "month":
        daily_average = current_year_total / 12
        average_label = "Per Month"
    else:
        daily_average = current_year_total / 365
        average_label = "Per Day"

    return {
        "total_emissions": round(current_year_total, 2),
        "daily_average": round(daily_average, 2),
        "average_label": average_label,
        "year_change_percent": round(year_change_percent, 1),
        "year_change_trend": (
            "increase"
            if year_change_percent > 0
            else "decrease" if year_change_percent < 0 else "stable"
        ),
        "last_year_total": round(last_year_total, 2),
        "daily_data": daily_data,
        "category_data": category_data,
        "materials_count": len(materials_list),
        "scope_data": scope_data,
        "selected_year": selected_year,
    }


@module.route("/update-badges", methods=["GET", "POST"])
@login_required
def update_badges():
    """HTMX endpoint สำหรับอัปเดต badges - แสดงเฉพาะ sub scopes ที่เลือก + อยู่ใน scopes ที่ติ๊ก"""
    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(user.campus_id, user.department_key)

    selected_scopes = session.get('selected_scopes', [])
    selected_sub_scopes = session.get('selected_sub_scopes', [])

    sub_scope_objects = []
    if selected_sub_scopes:
        try:
            scope_object_ids = [ObjectId(scope_id) for scope_id in selected_sub_scopes]
            all_sub_scopes = Scope.objects(
                id__in=scope_object_ids,
                campus=user.campus_id,
                department=user.department_key
            )

            if selected_scopes:
                sub_scope_objects = [
                    scope for scope in all_sub_scopes
                    if scope.ghg_scope in [int(s) for s in selected_scopes]
                ]
            else:
                sub_scope_objects = []
        except Exception as e:
            sub_scope_objects = []

    scope_badges = []
    
    if sub_scope_objects:
        scope_groups = {}
        for sub_scope in sub_scope_objects:
            main_scope = sub_scope.ghg_scope
            if main_scope not in scope_groups:
                scope_groups[main_scope] = []
            scope_groups[main_scope].append(sub_scope)

        for main_scope in sorted(scope_groups.keys()):
            total_sub_scopes = Scope.objects(
                campus=user.campus_id, 
                department=user.department_key, 
                ghg_scope=main_scope
            ).count()
            
            selected_in_scope = len(scope_groups[main_scope])
            
            if selected_in_scope == total_sub_scopes and total_sub_scopes > 0:
                scope_badges.append({
                    "type": "scope_all",
                    "text": f"Scope {main_scope} (ทั้งหมด)",
                    "class": "badge-success",
                })
            else:
                for sub_scope in scope_groups[main_scope]:
                    scope_badges.append({
                        "type": "sub_scope",
                        "text": f"Scope {sub_scope.ghg_scope}.{sub_scope.ghg_sup_scope}",
                        "class": "badge-info",
                    })

    return render_template(
        "/summary/partials/active_badges.html",
        selected_scopes=selected_scopes,
        sub_scope_objects=sub_scope_objects,
        scope_badges=scope_badges,
        user=user,
    )


@module.route("/years", methods=["GET"])
@login_required
def get_years():
    """HTMX endpoint สำหรับ load year dropdown"""
    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(user.campus_id, user.department_key)

    materials = Material.objects(campus=user.campus_id, department=user.department_key)
    years = sorted(list(set([m.year for m in materials if m.year])), reverse=True)

    if not years:
        years = [datetime.now().year]

    return render_template("/summary/partials/year_dropdown.html", years=years)


@module.route("/partials/top_sub_scope", methods=["GET"])
@login_required
def top_sub_scope_partial():
    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(user.campus_id, user.department_key)

    selected_scope = request.args.get("selected_scope", None)
    selectes_year = request.args.get("selected_year", datetime.now().year)

    scopes = Scope.objects(campus=user.campus_id, department=user.department_key)
    unique_scopes = {scope.ghg_scope: scope for scope in scopes}.values()

    top_sub_scopes = []
    total_emissions = 0
    if selected_scope and str(selected_scope).isdigit():
        sub_scopes = Scope.objects(
            campus=user.campus_id,
            department=user.department_key,
            ghg_scope=int(selected_scope),
        )
        sub_scope_results = []
        for sub_scope in sub_scopes:
            total_result = Material.objects(
                campus=user.campus_id,
                department=user.department_key,
                scope=sub_scope.ghg_scope,
                sub_scope=sub_scope.ghg_sup_scope,
                year=int(selectes_year),
            ).sum("result") or 0
            total_emissions += total_result
            sub_scope_results.append(
                {
                    "ghg_name": sub_scope.ghg_name,
                    "ghg_sup_scope": sub_scope.ghg_sup_scope,
                    "total_result": total_result,
                }
            )
        top_sub_scopes = sorted(
            sub_scope_results, key=lambda x: x["total_result"], reverse=True
        )[:3]

    return render_template(
        "/summary/partials/top_sub_scope.html",
        scopes=unique_scopes,
        top_sub_scopes=top_sub_scopes,
        selected_scope=int(selected_scope) if selected_scope and str(selected_scope).isdigit() else None,
        selected_year=int(selectes_year),
        total_emissions=total_emissions,
    )


@module.route("/sub-scope-popup", methods=["GET"])
@login_required
def sub_scope_popup():
    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(user.campus_id, user.department_key)
    
    selected_scopes = request.args.getlist('selected_scopes')
    current_selected_sub_scopes = session.get('selected_sub_scopes', [])
    
    if selected_scopes:
        sub_scopes = Scope.objects(
            campus=user.campus_id,
            department=user.department_key,
            ghg_scope__in=[int(scope) for scope in selected_scopes]
        ).order_by('ghg_scope', 'ghg_sup_scope')
    else:
        sub_scopes = []
    
    return render_template(
        "/summary/partials/sub_scope_popup.html", 
        sub_scopes=sub_scopes,
        current_selected_sub_scopes=current_selected_sub_scopes
    )


@module.route("/toggle-sub-scope", methods=["POST"])
@login_required
def toggle_sub_scope():
    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(user.campus_id, user.department_key)
    
    selected_scopes = request.form.getlist('selected_scopes')
    selected_sub_scopes = request.form.getlist('selected_sub_scopes')
    
    session['selected_scopes'] = selected_scopes
    session['selected_sub_scopes'] = selected_sub_scopes
    
    if selected_scopes:
        sub_scopes = Scope.objects(
            campus=user.campus_id,
            department=user.department_key,
            ghg_scope__in=[int(scope) for scope in selected_scopes]
        ).order_by('ghg_scope', 'ghg_sup_scope')
    else:
        sub_scopes = []
    
    return render_template(
        "/summary/partials/sub_scope_popup_content.html", 
        sub_scopes=sub_scopes,
        current_selected_sub_scopes=selected_sub_scopes
    )


@module.route("/select-all-sub-scopes", methods=["POST"])
@login_required
def select_all_sub_scopes():
    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(user.campus_id, user.department_key)
    
    selected_scopes = request.form.getlist('selected_scopes')
    
    if selected_scopes:
        sub_scopes = Scope.objects(
            campus=user.campus_id,
            department=user.department_key,
            ghg_scope__in=[int(scope) for scope in selected_scopes]
        ).order_by('ghg_scope', 'ghg_sup_scope')
        selected_sub_scopes = [str(sub_scope.id) for sub_scope in sub_scopes]
    else:
        sub_scopes = []
        selected_sub_scopes = []
    
    session['selected_scopes'] = selected_scopes
    session['selected_sub_scopes'] = selected_sub_scopes
    
    return render_template(
        "/summary/partials/sub_scope_popup_content.html", 
        sub_scopes=sub_scopes,
        current_selected_sub_scopes=selected_sub_scopes
    )


@module.route("/clear-all-sub-scopes", methods=["POST"])
@login_required
def clear_all_sub_scopes():
    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(user.campus_id, user.department_key)
    
    selected_scopes = request.form.getlist('selected_scopes')
    
    session['selected_scopes'] = selected_scopes
    session['selected_sub_scopes'] = []
    
    if selected_scopes:
        sub_scopes = Scope.objects(
            campus=user.campus_id,
            department=user.department_key,
            ghg_scope__in=[int(scope) for scope in selected_scopes]
        ).order_by('ghg_scope', 'ghg_sup_scope')
    else:
        sub_scopes = []
    
    return render_template(
        "/summary/partials/sub_scope_popup_content.html", 
        sub_scopes=sub_scopes,
        current_selected_sub_scopes=[]
    )


@module.route("/update-scope-selection", methods=["POST"])
@login_required
def update_scope_selection():
    """Update scope selection in session"""
    user = current_user
    selected_scopes = request.form.getlist("selected_scopes")
    session['selected_scopes'] = selected_scopes
    return {"status": "success"}


@module.route("/download-pdf-modal", methods=["GET"])
@login_required
@permissions_required_all(["เข้าถึงหน้าสรุปผล"])
def download_pdf_modal():
    """Show PDF download modal"""
    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(user.campus_id, user.department_key)
    
    selected_year = request.args.get("selected_year", datetime.now().year)
    
    return render_template(
        "/summary/partials/download_pdf_modal.html", 
        user=user,
        selected_year=selected_year
    )


@module.route("/preview-pdf-modal", methods=["GET"])
@login_required
@permissions_required_all(["เข้าถึงหน้าสรุปผล"])
def preview_pdf_modal():
    """Show PDF preview modal"""
    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(user.campus_id, user.department_key)

    # รับค่าฟิลเตอร์จาก request (query string)
    selected_year = request.args.get("selected_year", datetime.now().year)
    time_period = request.args.get("time_period", "week")
    selected_scopes = request.args.getlist("selected_scopes")
    selected_sub_scopes = request.args.getlist("selected_sub_scopes")

    # fallback: ถ้าไม่ได้ส่งมา ให้ใช้ session
    if not selected_scopes:
        selected_scopes = session.get('selected_scopes', [])
    if not selected_sub_scopes:
        selected_sub_scopes = session.get('selected_sub_scopes', [])

    # ถ้าไม่มี sub_scopes ให้ data เป็น 0
    if not selected_sub_scopes:
        data = {"total_emissions": 0, "daily_data": {}, "category_data": {}}
        last_year_data = {"total_emissions": 0, "daily_data": {}, "category_data": {}}
        bar_chart_base64 = ""
        last_year_bar_chart_base64 = ""
        category_chart_base64 = ""
        scope_emissions = {"Scope 1": 0, "Scope 2": 0, "Scope 3": 0}
        scope_breakdown_table = []
    else:
        data = calculate_emissions_data(user, selected_sub_scopes, time_period, int(selected_year))
        last_year_data = calculate_emissions_data(user, selected_sub_scopes, time_period, int(selected_year) - 1)
        bar_chart_base64 = generate_bar_chart_base64(data.get("daily_data", {}))
        last_year_bar_chart_base64 = generate_bar_chart_base64(last_year_data.get("daily_data", {}))
        category_chart_base64 = generate_category_chart_base64(data.get("category_data", {}))
        scope_emissions = {label: round(data["category_data"].get(label, 0), 2) for label in ["Scope 1", "Scope 2", "Scope 3"]}
        # เตรียมข้อมูลตาราง breakdown
        total = sum([data["category_data"].get(label, 0) for label in ["Scope 1", "Scope 2", "Scope 3"]])
        scope_breakdown_table = []
        for label, color in zip(["Scope 1", "Scope 2", "Scope 3"], ["#4f46e5", "#10b981", "#f97316"]):
            value = data["category_data"].get(label, 0)
            percent = (value / total * 100) if total > 0 else 0
            scope_breakdown_table.append({
                "scope": label,
                "value": round(value, 2),
                "percent": round(percent, 1),
                "color": color
            })

    return render_template(
        "/summary/partials/preview_pdf_modal.html",
        user=user,
        selected_year=selected_year,
        data=data,
        last_year_data=last_year_data,
        bar_chart_base64=bar_chart_base64,
        last_year_bar_chart_base64=last_year_bar_chart_base64,
        category_chart_base64=category_chart_base64,
        scope_emissions=scope_emissions,
        scope_breakdown_table=scope_breakdown_table
    )
def generate_bar_chart_base64(daily_data):
    """Generate a bar chart as base64 PNG from daily_data dict."""
    import matplotlib
    matplotlib.use('Agg')  # Use non-GUI backend
    import matplotlib.pyplot as plt
    import seaborn as sns
    sns.set_style('whitegrid', {'axes.facecolor': "#EAEAF2", 'grid.color': 'white', 'axes.edgecolor': '#EAEAF2'})
    import io
    import base64
    if not daily_data:
        return ""
    labels = [m[:3] for m in daily_data.keys()]
    values = list(daily_data.values())
    fig, ax = plt.subplots(figsize=(6, 3))
    # Add table-like background (alternating y bands)
    y_min, y_max = 0, max(values) if values else 1
    y_ticks = ax.get_yticks()
    for i in range(len(y_ticks)-1):
        if i % 2 == 0:
            ax.axhspan(y_ticks[i], y_ticks[i+1], facecolor="#f3f4f6", alpha=0.7, zorder=0)
    ax.bar(labels, values, color="#1e40af", zorder=2)
    ax.set_ylabel("Emissions (tCO₂e)")
    ax.set_xlabel("Month")
    ax.set_title("Emissions by Month")
    ax.grid(True, axis='y', linestyle='--', alpha=0.5, zorder=3)
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode("utf-8")
    return img_base64

def generate_category_chart_base64(category_data):
    """Generate a pie chart as base64 PNG from category_data dict."""
    import matplotlib
    matplotlib.use('Agg')  # Use non-GUI backend
    import matplotlib.pyplot as plt
    import io
    import base64
    import numpy as np
    if not category_data:
        return ""
    # สร้าง donut chart รวม Scope 1, 2, 3
    labels = ["Scope 1", "Scope 2", "Scope 3"]
    values = [category_data.get(label, 0) for label in labels]
    colors = ["#4f46e5", "#10b981", "#f97316"]
    fig, ax = plt.subplots(figsize=(3.8, 3.8))
    def autopct_func(pct):
        total = sum(values)
        val = int(round(pct * total / 100.0))
        return "%.1f%%" % pct if val > 0 else ""

    wedges, texts, autotexts = ax.pie(
        values,
        labels=None,  # ไม่แสดง label ติดกับ wedge
        autopct=autopct_func,
        colors=colors,
        startangle=90,
        wedgeprops={"edgecolor": "white", "linewidth": 2},
        textprops={"fontsize": 11, "weight": "bold"}
    )
    # ทำให้เป็น donut chart
    centre_circle = plt.Circle((0,0),0.70,fc='white')
    fig.gca().add_artist(centre_circle)
    ax.set_aspect("equal")
    # เพิ่ม leader line และ label scope แบบ custom ด้านนอก พร้อม % ต่อท้าย label
    total = sum(values)
    for i, w in enumerate(wedges):
        if values[i] > 0:
            ang = (w.theta2 + w.theta1)/2.
            percent = (values[i] / total * 100) if total > 0 else 0
            label_text = f"{labels[i]} ({percent:.1f}%)"
            # จุดปลายเส้น (label)
            label_x = 1.25 * np.cos(np.deg2rad(ang))
            label_y = 1.25 * np.sin(np.deg2rad(ang))
            # จุดเริ่มต้นเส้น (ขอบ donut)
            line_x = 0.85 * np.cos(np.deg2rad(ang))
            line_y = 0.85 * np.sin(np.deg2rad(ang))
            # วาดเส้นลากจาก donut ไป label
            ax.annotate(
                label_text,
                xy=(line_x, line_y),
                xytext=(label_x, label_y),
                ha='center', va='center',
                fontsize=12, fontweight='bold', color=colors[i],
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=colors[i], lw=1, alpha=0.8),
                arrowprops=dict(arrowstyle='-', color=colors[i], lw=1.5, alpha=0.7)
            )
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", transparent=True)
    plt.close(fig)
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode("utf-8")
    return img_base64


@module.route("/download-pdf", methods=["POST"])
@login_required
@permissions_required_all(["เข้าถึงหน้าสรุปผล"])
def download_pdf():
    """Generate and download PDF report of summary"""
    try:
        import io
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import urllib.parse
        import json
        from flask import make_response, send_file
        
        # Get form data
        report_title = request.form.get("report_title", "รายงานสรุปผล Carbon Footprint")
        notes = request.form.get("notes", "")
        pdf_format = request.form.get("pdf_format", "summary")
        is_htmx = request.form.get("htmx_request") == "1"
        
        # Get user info
        user = current_user
        user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
        user.department = CampusAndDepartment.get_department_name(user.campus_id, user.department_key)
        
        # Get selected data from session and form
        selected_scopes = session.get('selected_scopes', []) or request.form.getlist("selected_scopes")
        selected_sub_scopes = session.get('selected_sub_scopes', []) or request.form.getlist("selected_sub_scopes")
        selected_year = request.form.get("selected_year", datetime.now().year)
        time_period = request.form.get("time_period", "week")
        
        if not selected_sub_scopes:
            if is_htmx:
                return create_htmx_response(
                    "/components/toast-notification.html",
                    error_message="กรุณาเลือก Sub Scope ก่อนสร้างรายงาน"
                )
            return jsonify({"error": "กรุณาเลือก Sub Scope ก่อนสร้างรายงาน"}), 400
        
        # Calculate data using existing function
        data = calculate_emissions_data(user, selected_sub_scopes, time_period, int(selected_year))
        
        # Register Thai font
        try:
            # Try Windows fonts first
            thai_font_name = "TH-Sarabun-PSK"
            thai_font_bold = "TH-Sarabun-PSK-Bold"
            
            try:
                pdfmetrics.registerFont(TTFont(thai_font_name, "C:/Windows/Fonts/THSarabunPSK.ttf"))
                pdfmetrics.registerFont(TTFont(thai_font_bold, "C:/Windows/Fonts/THSarabunPSKBold.ttf"))
            except:
                # Fallback fonts
                thai_font_name = "Helvetica"
                thai_font_bold = "Helvetica-Bold"
        except Exception as e:
            thai_font_name = "Helvetica"
            thai_font_bold = "Helvetica-Bold"
        
        # Create PDF
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
        styles = getSampleStyleSheet()
        
        # Define styles
        title_style = ParagraphStyle(
            'SummaryTitle',
            parent=styles['Heading1'],
            fontSize=20,
            spaceAfter=10,
            textColor=colors.Color(30/255, 64/255, 175/255),
            alignment=1,
            fontName=thai_font_bold,
            keepWithNext=True
        )
        
        # Create story
        story = []
        
        # Title
        story.append(Paragraph(report_title, title_style))
        story.append(Spacer(1, 20))
        
        # Meta info
        generated_date = datetime.now().strftime("%d/%m/%Y %H:%M")
        meta_data = [
            ['Campus:', user.campus, 'Year:', str(selected_year)],
            ['Department:', user.department, 'สร้างรายงานเมื่อ:', generated_date],
            ['Time Period:', time_period, 'Total Scopes:', str(len(selected_scopes))],
        ]
        
        meta_table = Table(meta_data, colWidths=[1.5*inch, 2.0*inch, 1.5*inch, 2.5*inch])
        meta_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), thai_font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 20))
        
        # Summary statistics
        summary_data = [
            ['Total CO₂ Emissions:', f"{data['total_emissions']:,.2f} tCO₂e"],
            ['Average per Period:', f"{data['daily_average']:,.2f} tCO₂e"],
            ['Year Change:', f"{data['year_change_percent']:+.1f}% ({data['year_change_trend']})"],
            ['Materials Count:', str(data['materials_count'])],
        ]
        
        summary_table = Table(summary_data, colWidths=[3*inch, 3*inch])
        summary_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), thai_font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 20))
        
        # Scope breakdown if detailed format
        if pdf_format == "detailed" and data['scope_data']:
            scope_header = Paragraph("Scope Breakdown", styles['Heading2'])
            story.append(scope_header)
            story.append(Spacer(1, 10))
            
            scope_data_table = [['Scope', 'Sub Scope', 'Emissions (tCO₂e)', 'Percentage']]
            
            for scope_key, scope_info in data['scope_data'].items():
                percentage = (scope_info['emissions'] / data['total_emissions'] * 100) if data['total_emissions'] > 0 else 0
                scope_data_table.append([
                    f"Scope {scope_info['ghg_scope']}",
                    f"{scope_info['ghg_sup_scope']}",
                    f"{scope_info['emissions']:,.2f}",
                    f"{percentage:.1f}%"
                ])
            
            scope_table = Table(scope_data_table, colWidths=[1.5*inch, 1.5*inch, 2*inch, 1.5*inch])
            scope_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), thai_font_name),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('FONTNAME', (0, 0), (-1, 0), thai_font_bold),
            ]))
            story.append(scope_table)
        
        # Notes
        if notes.strip():
            story.append(Spacer(1, 20))
            notes_header = Paragraph("หมายเหตุ", styles['Heading3'])
            story.append(notes_header)
            notes_para = Paragraph(notes, styles['Normal'])
            story.append(notes_para)
        
        # Build PDF
        doc.build(story)
        pdf_buffer.seek(0)
        
        # Create response
        filename = f"summary_report_{selected_year}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        if is_htmx:
            # For HTMX request, return success message
            response_html = f"""
            <div class="modal modal-open">
              <div class="modal-box">
                <h3 class="font-bold text-lg text-success">สร้างรายงานสำเร็จ!</h3>
                <p class="py-4">รายงาน PDF ของคุณพร้อมดาวน์โหลดแล้ว</p>
                <div class="modal-action">
                  <a href="data:application/pdf;base64,{base64.b64encode(pdf_buffer.getvalue()).decode()}" 
                     download="{filename}"
                     class="btn btn-success">
                    <i data-feather="download" class="w-4 h-4 mr-2"></i>
                    ดาวน์โหลด PDF
                  </a>
                  <button class="btn btn-ghost" onclick="this.closest('.modal').remove()">ปิด</button>
                </div>
              </div>
            </div>
            <script>feather.replace();</script>
            """
            return response_html
        else:
            # For direct request, return PDF file
            return send_file(
                pdf_buffer,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=filename
            )
            
    except Exception as e:
        if is_htmx:
            return create_htmx_response(
                "/components/toast-notification.html",
                error_message=f"เกิดข้อผิดพลาดในการสร้างรายงาน: {str(e)}"
            )
        return jsonify({"error": f"เกิดข้อผิดพลาดในการสร้างรายงาน: {str(e)}"}), 500


def create_htmx_response(template_path, template_vars=None, success_message=None, error_message=None):
    """Helper function for creating HTMX response with toast notification"""
    if template_vars is None:
        template_vars = {}
    
    from flask import make_response, render_template
    
    response = make_response(render_template(template_path, **template_vars))
    
    trigger_data = {}
    if success_message:
        trigger_data["showSuccess"] = urllib.parse.quote(success_message)
    if error_message:
        trigger_data["showError"] = urllib.parse.quote(error_message)
    
    if trigger_data:
        response.headers['HX-Trigger'] = json.dumps(trigger_data)
    
    return response
    """HTMX endpoint สำหรับอัปเดต scope selection"""
    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(user.campus_id, user.department_key)
    
    selected_scopes = request.form.getlist("selected_scopes")
    previous_selected_scopes = session.get('selected_scopes', [])
    current_selected_sub_scopes = session.get('selected_sub_scopes', [])
    
    if not hasattr(request, 'form') or 'selected_scopes' not in request.form:
        return ""
    
    session['selected_scopes'] = selected_scopes
    
    removed_scopes = list(set(previous_selected_scopes) - set(selected_scopes))
    
    if current_selected_sub_scopes and removed_scopes:
        scope_object_ids = [ObjectId(scope_id) for scope_id in current_selected_sub_scopes]
        all_selected_sub_scopes = Scope.objects(
            id__in=scope_object_ids,
            campus=user.campus_id,
            department=user.department_key
        )
        
        remaining_sub_scopes = [
            str(scope.id) for scope in all_selected_sub_scopes
            if scope.ghg_scope not in [int(s) for s in removed_scopes]
        ]
        
        session['selected_sub_scopes'] = remaining_sub_scopes
    
    return ""




    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(user.campus_id, user.department_key)

    # Mock: ดึง scopes/subscopes/ปี/ช่วงเวลา จาก session หรือ default
    selected_scopes = session.get('selected_scopes', [])
    selected_sub_scopes = session.get('selected_sub_scopes', [])
    selected_year = session.get('selected_year', datetime.now().year)
    time_period = session.get('selected_time_period', 'month')

    # ถ้าไม่มี subscopes ให้ส่งข้อมูลว่าง
    if not selected_sub_scopes:
        data = {
            'daily_data': {},
            'category_data': {},
            'total_emissions': 0,
            'daily_average': 0,
            'average_label': '',
            'year_change_percent': 0,
            'year_change_trend': 'stable',
            'last_year_total': 0,
            'materials_count': 0,
            'scope_data': {},
        }
    else:
        # เรียกฟังก์ชันคำนวณข้อมูล summary
        data = calculate_emissions_data(
            user,
            selected_sub_scopes,
            time_period,
            selected_year
        )

    return render_template(
        'summary/partials/preview_pdf_modal.html',
        user=user,
        selected_year=selected_year,
        data=data
    )



