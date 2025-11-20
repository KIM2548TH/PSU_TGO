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
    user.department = CampusAndDepartment.get_department_name(
        user.campus_id, user.department_key
    )
    return render_template("/summary/summary.html", user=user)


@module.route("/scopes", methods=["GET"])
@login_required
def get_scopes():
    """HTMX endpoint สำหรับ load scope dropdown"""
    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(
        user.campus_id, user.department_key
    )

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
    user.department = CampusAndDepartment.get_department_name(
        user.campus_id, user.department_key
    )

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
    user.department = CampusAndDepartment.get_department_name(
        user.campus_id, user.department_key
    )

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
            campus=user.campus_id,
            department=user.department_key,
            ghg_sup_scope=sub_scope_id,
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
    user.department = CampusAndDepartment.get_department_name(
        user.campus_id, user.department_key
    )

    form_selected_scopes = request.form.getlist("selected_scopes")
    form_selected_sub_scopes = request.form.getlist("selected_sub_scopes")
    if form_selected_scopes:
        session["selected_scopes"] = form_selected_scopes
    if form_selected_sub_scopes:
        session["selected_sub_scopes"] = form_selected_sub_scopes

    selected_scopes = form_selected_scopes or session.get("selected_scopes", [])
    selected_sub_scopes = form_selected_sub_scopes or session.get(
        "selected_sub_scopes", []
    )
    time_period = request.form.get("time_period", "week")
    selected_year = request.form.get("selected_year", datetime.now().year)

    if not selected_sub_scopes:
        return """
    <div id="stats-container" class="mb-6">
      <div class="text-center text-gray-500 p-8 bg-white rounded-lg shadow-sm">
        <i data-feather="bar-chart-2" class="w-8 h-8 sm:w-12 sm:h-12 mx-auto mb-4 text-gray-300"></i>
        <p class="text-base sm:text-lg">Select Sub Scopes to view statistics</p>
      </div>
    </div>
    <script>if (window.feather) feather.replace();</script>
    """

    scope_object_ids = [ObjectId(x) for x in selected_sub_scopes]
    all_selected_sub_scopes = Scope.objects(
        id__in=scope_object_ids, campus=user.campus_id, department=user.department_key
    )

    if selected_scopes:
        valid_sub_scopes = [
            s
            for s in all_selected_sub_scopes
            if s.ghg_scope in [int(v) for v in selected_scopes]
        ]
    else:
        valid_sub_scopes = list(all_selected_sub_scopes)

    valid_ids = [str(s.id) for s in valid_sub_scopes]

    if not valid_ids:
        return """
    <div id="stats-container" class="mb-6">
      <div class="text-center text-gray-500 p-8 bg-white rounded-lg shadow-sm">
        <i data-feather="bar-chart-2" class="w-8 h-8 sm:w-12 sm:h-12 mx-auto mb-4 text-gray-300"></i>
        <p class="text-base sm:text-lg">Select Scopes to view data</p>
      </div>
    </div>
    <script>if (window.feather) feather.replace();</script>
    """

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
    user.department = CampusAndDepartment.get_department_name(
        user.campus_id, user.department_key
    )

    form_selected_scopes = request.form.getlist("selected_scopes")
    form_selected_sub_scopes = request.form.getlist("selected_sub_scopes")
    if form_selected_scopes:
        session["selected_scopes"] = form_selected_scopes
    if form_selected_sub_scopes:
        session["selected_sub_scopes"] = form_selected_sub_scopes

    selected_scopes = form_selected_scopes or session.get("selected_scopes", [])
    selected_sub_scopes = form_selected_sub_scopes or session.get(
        "selected_sub_scopes", []
    )
    time_period = request.form.get("time_period", "week")
    selected_year = int(request.form.get("selected_year", datetime.now().year))

    if not selected_sub_scopes:
        return """
    <div id="charts-container">
      <div class="text-center text-gray-500 p-8 bg-white rounded-lg shadow-sm">
        <i data-feather="pie-chart" class="w-8 h-8 sm:w-12 sm:h-12 mx-auto mb-4 text-gray-300"></i>
        <p class="text-base sm:text-lg">Select Sub Scopes to view charts</p>
      </div>
    </div>
    <script>if (window.feather) feather.replace();</script>
    """

    scope_object_ids = [ObjectId(x) for x in selected_sub_scopes]
    all_selected_sub_scopes = Scope.objects(
        id__in=scope_object_ids, campus=user.campus_id, department=user.department_key
    )

    if selected_scopes:
        valid_sub_scopes = [
            s
            for s in all_selected_sub_scopes
            if s.ghg_scope in [int(v) for v in selected_scopes]
        ]
    else:
        valid_sub_scopes = list(all_selected_sub_scopes)

    valid_ids = [str(s.id) for s in valid_sub_scopes]

    if not valid_ids:
        return """
    <div id="charts-container">
      <div class="text-center text-gray-500 p-8 bg-white rounded-lg shadow-sm">
        <i data-feather="pie-chart" class="w-8 h-8 sm:w-12 sm:h-12 mx-auto mb-4 text-gray-300"></i>
        <p class="text-base sm:text-lg">Select Scopes to view charts</p>
      </div>
    </div>
    <script>if (window.feather) feather.replace();</script>
    """

    current_year_data = calculate_emissions_data(
        user, valid_ids, time_period, selected_year
    )
    previous_year_data = calculate_emissions_data(
        user, valid_ids, time_period, selected_year - 1
    )

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

    scope_pairs = list(
        set([(scope.ghg_scope, scope.ghg_sup_scope) for scope in scopes])
    )

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
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
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
            m
            for m in materials_list
            if m.scope == ghg_scope and m.sub_scope == ghg_sup_scope
        ]
        emissions = sum(m.result2 or 0 for m in scope_materials)

        category_data[scope_name] = category_data.get(scope_name, 0) + emissions

        scope_key = f"Scope {ghg_scope}.{ghg_sup_scope}"

        scope_object = next(
            (
                s
                for s in scopes
                if s.ghg_scope == ghg_scope and s.ghg_sup_scope == ghg_sup_scope
            ),
            None,
        )

        scope_data[scope_key] = {
            "ghg_scope": ghg_scope,
            "ghg_sup_scope": ghg_sup_scope,
            "emissions": emissions,
            "scope_object": scope_object,
            "ghg_name": (
                scope_object.ghg_name
                if scope_object
                else f"Scope {ghg_scope}.{ghg_sup_scope}"
            ),
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
    user.department = CampusAndDepartment.get_department_name(
        user.campus_id, user.department_key
    )

    selected_scopes = session.get("selected_scopes", [])
    selected_sub_scopes = session.get("selected_sub_scopes", [])

    sub_scope_objects = []
    if selected_sub_scopes:
        try:
            scope_object_ids = [ObjectId(scope_id) for scope_id in selected_sub_scopes]
            all_sub_scopes = Scope.objects(
                id__in=scope_object_ids,
                campus=user.campus_id,
                department=user.department_key,
            )

            if selected_scopes:
                sub_scope_objects = [
                    scope
                    for scope in all_sub_scopes
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
                ghg_scope=main_scope,
            ).count()

            selected_in_scope = len(scope_groups[main_scope])

            if selected_in_scope == total_sub_scopes and total_sub_scopes > 0:
                scope_badges.append(
                    {
                        "type": "scope_all",
                        "text": f"Scope {main_scope} (ทั้งหมด)",
                        "class": "badge-success",
                    }
                )
            else:
                for sub_scope in scope_groups[main_scope]:
                    scope_badges.append(
                        {
                            "type": "sub_scope",
                            "text": f"Scope {sub_scope.ghg_scope}.{sub_scope.ghg_sup_scope}",
                            "class": "badge-info",
                        }
                    )

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
    user.department = CampusAndDepartment.get_department_name(
        user.campus_id, user.department_key
    )

    materials = Material.objects(campus=user.campus_id, department=user.department_key)
    years = sorted(list(set([m.year for m in materials if m.year])))

    if not years:
        years = [datetime.now().year]

    return render_template("/summary/partials/year_dropdown.html", years=years)


@module.route("/partials/top_sub_scope", methods=["GET"])
@login_required
def top_sub_scope_partial():
    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(
        user.campus_id, user.department_key
    )

    selected_scope = request.args.get("selected_scope", None)
    selected_year = request.args.get("selected_year", datetime.now().year)

    scopes = Scope.objects(campus=user.campus_id, department=user.department_key)
    unique_scopes = {scope.ghg_scope: scope for scope in scopes}.values()

    top_materials = []
    total_emissions = 0

    if selected_scope == "all":
        # Aggregate result2 by material name across all scopes
        materials = Material.objects(
            campus=user.campus_id,
            department=user.department_key,
            year=int(selected_year),
            result2__exists=True,
            result2__ne=0,
        )

        # Aggregate by name
        from collections import defaultdict

        agg = defaultdict(lambda: {"result2": 0, "scopes": set()})
        for m in materials:
            agg[m.name]["result2"] += m.result2 or 0
            agg[m.name]["scopes"].add((m.scope, m.sub_scope))

        # Convert to list and sort by result2 desc
        agg_list = [
            {
                "head": name,
                "result2": data["result2"],
                "scope_name": ", ".join(
                    [f"Scope {s[0]}.{s[1]}" for s in sorted(data["scopes"])]
                ),
            }
            for name, data in agg.items()
        ]
        agg_list = sorted(agg_list, key=lambda x: x["result2"], reverse=True)[:3]
        total_emissions = sum(x["result2"] for x in agg_list)
        top_materials = agg_list

    elif selected_scope and str(selected_scope).isdigit():
        # Get top materials from specific scope using result2
        materials = Material.objects(
            campus=user.campus_id,
            department=user.department_key,
            scope=int(selected_scope),
            year=int(selected_year),
            result2__exists=True,
            result2__ne=0,
        ).order_by("-result2")[:3]

        for material in materials:
            # Get scope information for each material
            scope_obj = None
            try:
                scope_obj = Scope.objects(
                    campus=user.campus_id,
                    department=user.department_key,
                    ghg_scope=material.scope,
                    ghg_sup_scope=material.sub_scope,
                ).first()
            except:
                pass

            scope_name = f"Scope {material.scope}.{material.sub_scope}"
            if scope_obj and scope_obj.ghg_name:
                scope_name = scope_obj.ghg_name

            result2_value = material.result2 or 0
            total_emissions += result2_value

            top_materials.append(
                {
                    "head": material.name,
                    "result2": result2_value,
                    "scope_name": scope_name,
                }
            )

    return render_template(
        "/summary/partials/top_sub_scope.html",
        scopes=unique_scopes,
        top_materials=top_materials,
        selected_scope=(
            selected_scope
            if selected_scope == "all"
            else (
                int(selected_scope)
                if selected_scope and str(selected_scope).isdigit()
                else None
            )
        ),
        selected_year=int(selected_year),
        total_emissions=total_emissions,
    )


@module.route("/sub-scope-popup", methods=["GET"])
@login_required
def sub_scope_popup():
    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(
        user.campus_id, user.department_key
    )

    selected_scopes = request.args.getlist("selected_scopes")
    current_selected_sub_scopes = session.get("selected_sub_scopes", [])

    if selected_scopes:
        sub_scopes = Scope.objects(
            campus=user.campus_id,
            department=user.department_key,
            ghg_scope__in=[int(scope) for scope in selected_scopes],
        ).order_by("ghg_scope", "ghg_sup_scope")
    else:
        sub_scopes = []

    return render_template(
        "/summary/partials/sub_scope_popup.html",
        sub_scopes=sub_scopes,
        current_selected_sub_scopes=current_selected_sub_scopes,
    )


@module.route("/toggle-sub-scope", methods=["POST"])
@login_required
def toggle_sub_scope():
    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(
        user.campus_id, user.department_key
    )

    selected_scopes = request.form.getlist("selected_scopes")
    selected_sub_scopes = request.form.getlist("selected_sub_scopes")

    session["selected_scopes"] = selected_scopes
    session["selected_sub_scopes"] = selected_sub_scopes

    if selected_scopes:
        sub_scopes = Scope.objects(
            campus=user.campus_id,
            department=user.department_key,
            ghg_scope__in=[int(scope) for scope in selected_scopes],
        ).order_by("ghg_scope", "ghg_sup_scope")
    else:
        sub_scopes = []

    return render_template(
        "/summary/partials/sub_scope_popup_content.html",
        sub_scopes=sub_scopes,
        current_selected_sub_scopes=selected_sub_scopes,
    )


@module.route("/select-all-sub-scopes", methods=["POST"])
@login_required
def select_all_sub_scopes():
    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(
        user.campus_id, user.department_key
    )

    selected_scopes = request.form.getlist("selected_scopes")

    if selected_scopes:
        sub_scopes = Scope.objects(
            campus=user.campus_id,
            department=user.department_key,
            ghg_scope__in=[int(scope) for scope in selected_scopes],
        ).order_by("ghg_scope", "ghg_sup_scope")
        selected_sub_scopes = [str(sub_scope.id) for sub_scope in sub_scopes]
    else:
        sub_scopes = []
        selected_sub_scopes = []

    session["selected_scopes"] = selected_scopes
    session["selected_sub_scopes"] = selected_sub_scopes

    return render_template(
        "/summary/partials/sub_scope_popup_content.html",
        sub_scopes=sub_scopes,
        current_selected_sub_scopes=selected_sub_scopes,
    )


@module.route("/clear-all-sub-scopes", methods=["POST"])
@login_required
def clear_all_sub_scopes():
    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(
        user.campus_id, user.department_key
    )

    selected_scopes = request.form.getlist("selected_scopes")

    session["selected_scopes"] = selected_scopes
    session["selected_sub_scopes"] = []

    if selected_scopes:
        sub_scopes = Scope.objects(
            campus=user.campus_id,
            department=user.department_key,
            ghg_scope__in=[int(scope) for scope in selected_scopes],
        ).order_by("ghg_scope", "ghg_sup_scope")
    else:
        sub_scopes = []

    return render_template(
        "/summary/partials/sub_scope_popup_content.html",
        sub_scopes=sub_scopes,
        current_selected_sub_scopes=[],
    )


@module.route("/update-scope-selection", methods=["POST"])
@login_required
def update_scope_selection():
    """Update scope selection in session"""
    user = current_user
    selected_scopes = request.form.getlist("selected_scopes")
    session["selected_scopes"] = selected_scopes
    return {"status": "success"}


@module.route("/download-pdf-modal", methods=["GET"])
@login_required
@permissions_required_all(["โหลดรายงานสรุปผล PDF"])
def download_pdf_modal():
    """Show PDF download modal"""
    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(
        user.campus_id, user.department_key
    )

    selected_year = request.args.get("selected_year", datetime.now().year)

    return render_template(
        "/summary/partials/download_pdf_modal.html",
        user=user,
        selected_year=selected_year,
    )


@module.route("/preview-pdf-modal", methods=["GET"])
@login_required
@permissions_required_all(["ดูตัวอย่างสรุปผล PDF"])
def preview_pdf_modal():
    """Show PDF preview modal"""
    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(
        user.campus_id, user.department_key
    )

    # รับค่าฟิลเตอร์จาก request (query string)
    selected_year = request.args.get("selected_year", datetime.now().year)
    time_period = request.args.get("time_period", "week")
    selected_scopes = request.args.getlist("selected_scopes")
    selected_sub_scopes = request.args.getlist("selected_sub_scopes")

    # fallback: ถ้าไม่ได้ส่งมา ให้ใช้ session
    if not selected_scopes:
        selected_scopes = session.get("selected_scopes", [])
    if not selected_sub_scopes:
        selected_sub_scopes = session.get("selected_sub_scopes", [])

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
        data = calculate_emissions_data(
            user, selected_sub_scopes, time_period, int(selected_year)
        )
        last_year_data = calculate_emissions_data(
            user, selected_sub_scopes, time_period, int(selected_year) - 1
        )
        bar_chart_base64 = generate_bar_chart_base64(data.get("daily_data", {}))
        last_year_bar_chart_base64 = generate_bar_chart_base64(
            last_year_data.get("daily_data", {})
        )
        category_chart_base64 = generate_category_chart_base64(
            data.get("category_data", {})
        )
        scope_emissions = {
            label: round(data["category_data"].get(label, 0), 2)
            for label in ["Scope 1", "Scope 2", "Scope 3"]
        }
        # เตรียมข้อมูลตาราง breakdown
        total = sum(
            [
                data["category_data"].get(label, 0)
                for label in ["Scope 1", "Scope 2", "Scope 3"]
            ]
        )
        scope_breakdown_table = []
        for label, color in zip(
            ["Scope 1", "Scope 2", "Scope 3"], ["#4f46e5", "#10b981", "#f97316"]
        ):
            value = data["category_data"].get(label, 0)
            percent = (value / total * 100) if total > 0 else 0
            scope_breakdown_table.append(
                {
                    "scope": label,
                    "value": round(value, 2),
                    "percent": round(percent, 1),
                    "color": color,
                }
            )

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
        scope_breakdown_table=scope_breakdown_table,
    )


def generate_bar_chart_base64(current_data, previous_data=None):
    """Generate a grouped bar chart as base64 PNG comparing current and previous year monthly tCO₂e."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    sns.set_style(
        "whitegrid",
        {
            "axes.facecolor": "#EAEAF2",
            "grid.color": "white",
            "axes.edgecolor": "#EAEAF2",
        },
    )
    import io
    import base64

    month_names = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
    month_labels = [m[:3] for m in month_names]
    current_values = [current_data.get(m, 0) for m in month_names]
    previous_values = (
        [previous_data.get(m, 0) for m in month_names] if previous_data else None
    )
    fig, ax = plt.subplots(figsize=(6, 3))
    y_min, y_max = 0, (
        max(current_values + (previous_values if previous_values else []))
        if (current_values or previous_values)
        else 1
    )
    y_ticks = ax.get_yticks()
    for i in range(len(y_ticks) - 1):
        if i % 2 == 0:
            ax.axhspan(
                y_ticks[i], y_ticks[i + 1], facecolor="#f3f4f6", alpha=0.7, zorder=0
            )
    bar_width = 0.35
    x = range(len(month_labels))
    # Buddhist year conversion
    from datetime import datetime

    current_year = datetime.now().year
    # If current_data is for selected_year, previous_data is for selected_year-1
    # Try to infer year from data length (assume always 12 months)
    # But safer to pass year as argument, so get from caller if possible
    # For now, get from global scope (download_pdf)
    # Use colors: current year (#10B981), previous year (#4F46E5)
    # Legend labels: ปี พ.ศ. (ตัวเลข)
    # Try to get year from caller
    import inspect

    frame = inspect.currentframe()
    caller_locals = frame.f_back.f_locals if frame and frame.f_back else {}
    selected_year = caller_locals.get("selected_year", current_year)
    current_year_th = int(selected_year) + 543
    previous_year_th = int(selected_year) - 1 + 543
    ax.bar(
        [i - bar_width / 2 for i in x],
        previous_values if previous_values else [0] * 12,
        width=bar_width,
        color="#4F46E5",
        label=f"{int(selected_year)-1}",
        zorder=2,
    )
    ax.bar(
        [i + bar_width / 2 for i in x],
        current_values,
        width=bar_width,
        color="#10B981",
        label=f"{int(selected_year)}",
        zorder=2,
    )
    ax.set_ylabel("Emissions (tCO$_2$e)")
    ax.set_xlabel("Month")
    ax.set_title("Emissions by Month")
    ax.set_xticks(x)
    ax.set_xticklabels(month_labels, rotation=30, ha="right")
    ax.grid(True, axis="y", linestyle="--", alpha=0.5, zorder=3)
    # Set Thai font for legend
    thai_font_path = None
    try:
        import os

        base_dir = os.path.dirname(os.path.abspath(__file__))
        font_dir = os.path.join(base_dir, "..", "static", "fonts")
        font_dir = os.path.abspath(font_dir)
        thai_font_path = os.path.join(font_dir, "Sarabun-Regular.ttf")
        if os.path.exists(thai_font_path):
            from matplotlib import font_manager

            font_prop = font_manager.FontProperties(fname=thai_font_path)
        else:
            font_prop = None
    except Exception:
        font_prop = None
    legend = ax.legend(
        title="ปี ค.ศ.",
        prop=font_prop,
        title_fontproperties=font_prop,
        loc="upper right",
        bbox_to_anchor=(1.12, 1),
    )
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

    matplotlib.use("Agg")  # Use non-GUI backend
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
    # Always set aspect ratio to equal for perfect circle
    ax.set_aspect("equal", adjustable="datalim")
    wedges, texts = ax.pie(
        values,
        labels=None,  # ไม่แสดง label ติดกับ wedge
        colors=colors,
        startangle=90,
        wedgeprops={"edgecolor": "white", "linewidth": 2},
        textprops={"fontsize": 11, "weight": "bold"},
    )
    # ทำให้เป็น donut chart
    centre_circle = plt.Circle((0, 0), 0.70, fc="white")
    fig.gca().add_artist(centre_circle)
    ax.set_aspect("equal")
    # เพิ่ม leader line และ label scope แบบ custom ด้านนอก พร้อม % ต่อท้าย label
    total = sum(values)
    for i, w in enumerate(wedges):
        if values[i] > 0:
            ang = (w.theta2 + w.theta1) / 2.0
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
                ha="center",
                va="center",
                fontsize=12,
                fontweight="bold",
                color=colors[i],
                bbox=dict(
                    boxstyle="round,pad=0.3", fc="white", ec=colors[i], lw=1, alpha=0.8
                ),
                arrowprops=dict(arrowstyle="-", color=colors[i], lw=1.5, alpha=0.7),
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
@permissions_required_all(["โหลดรายงานสรุปผล PDF"])
def download_pdf():
    """Generate and download PDF report of summary using reportlab only"""
    try:
        import io
        from flask import send_file
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
            Image,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import base64
        import urllib.parse
        import json
        import tempfile
        import os

        # Get form data
        report_title = request.form.get("report_title", "รายงานสรุปผล Carbon Footprint")
        notes = request.form.get("notes", "")
        pdf_format = request.form.get("pdf_format", "detailed")
        is_htmx = request.form.get("htmx_request") == "1"

        # Get user info
        user = current_user
        user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
        user.department = CampusAndDepartment.get_department_name(
            user.campus_id, user.department_key
        )

        # Get selected data from session and form
        selected_scopes = session.get("selected_scopes", []) or request.form.getlist(
            "selected_scopes"
        )
        selected_sub_scopes = session.get(
            "selected_sub_scopes", []
        ) or request.form.getlist("selected_sub_scopes")
        selected_year = request.form.get("selected_year", datetime.now().year)
        time_period = request.form.get("time_period", "week")

        if not selected_sub_scopes:
            if is_htmx:
                return create_htmx_response(
                    "/components/toast-notification.html",
                    error_message="กรุณาเลือก Sub Scope ก่อนสร้างรายงาน",
                )
            return jsonify({"error": "กรุณาเลือก Sub Scope ก่อนสร้างรายงาน"}), 400

        # Prepare data
        data = calculate_emissions_data(
            user, selected_sub_scopes, time_period, int(selected_year)
        )
        last_year_data = calculate_emissions_data(
            user, selected_sub_scopes, time_period, int(selected_year) - 1
        )
        bar_chart_base64 = generate_bar_chart_base64(
            data.get("daily_data", {}), last_year_data.get("daily_data", {})
        )
        category_chart_base64 = generate_category_chart_base64(
            data.get("category_data", {})
        )
        scope_emissions = {
            label: round(data["category_data"].get(label, 0), 2)
            for label in ["Scope 1", "Scope 2", "Scope 3"]
        }
        total = sum(
            [
                data["category_data"].get(label, 0)
                for label in ["Scope 1", "Scope 2", "Scope 3"]
            ]
        )
        scope_breakdown_table = []
        for label, color in zip(
            ["Scope 1", "Scope 2", "Scope 3"], ["#4f46e5", "#10b981", "#f97316"]
        ):
            value = data["category_data"].get(label, 0)
            percent = (value / total * 100) if total > 0 else 0
            scope_breakdown_table.append(
                {
                    "scope": label,
                    "value": round(value, 2),
                    "percent": round(percent, 1),
                    "color": color,
                }
            )

        # Register Thai font (use static/fonts like emission_proportions_view)
        try:
            import os

            base_dir = os.path.dirname(os.path.abspath(__file__))
            font_dir = os.path.join(base_dir, "..", "static", "fonts")
            font_dir = os.path.abspath(font_dir)
            thai_font_path = os.path.join(font_dir, "Sarabun-Regular.ttf")
            bold_font_path = os.path.join(font_dir, "Sarabun-Bold.ttf")

            if os.path.exists(thai_font_path):
                pdfmetrics.registerFont(TTFont("Sarabun", thai_font_path))
                thai_font_name = "Sarabun"
            else:
                thai_font_name = "Helvetica"
            if os.path.exists(bold_font_path):
                pdfmetrics.registerFont(TTFont("Sarabun-Bold", bold_font_path))
                thai_font_bold = "Sarabun-Bold"
            else:
                thai_font_bold = "Helvetica-Bold"
        except Exception as e:
            print(f"❌ Font loading error: {str(e)}")
            thai_font_name = "Helvetica"
            thai_font_bold = "Helvetica-Bold"

        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            pdf_buffer, pagesize=A4, topMargin=0.5 * inch, bottomMargin=0.5 * inch
        )
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "SummaryTitle",
            parent=styles["Heading1"],
            fontSize=20,
            spaceAfter=10,
            textColor=colors.Color(30 / 255, 64 / 255, 175 / 255),
            alignment=1,
            fontName=thai_font_bold,
            keepWithNext=True,
        )

        story = []
        # Title
        story.append(Paragraph(report_title, title_style))
        story.append(Spacer(1, 8))
        # University name only (center)
        uni_style = ParagraphStyle(
            "UniName",
            parent=styles["Normal"],
            fontSize=13,
            alignment=1,
            fontName=thai_font_name,
            textColor=colors.HexColor("#444"),
        )
        story.append(Paragraph("มหาวิทยาลัยสงขลานครินทร์", uni_style))
        story.append(Spacer(1, 16))

        # Meta info table: 2 items per row for clarity
        generated_date = datetime.now().strftime("%d/%m/%Y %H:%M")
        meta_data = [
            [f"Campus: {user.campus}", f"Department: {user.department}"],
            [f"Year: {selected_year}", f"Time Period: {time_period}"],
            [
                f"สร้างรายงานเมื่อ: {generated_date}",
                f"Total Scopes: {len(selected_scopes)}",
            ],
        ]
        meta_table = Table(meta_data, colWidths=[3.2 * inch, 3.2 * inch])
        meta_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), thai_font_name),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(meta_table)
        story.append(Spacer(1, 20))

        # Summary cards (horizontal row, value above label, equal height)
        # Card colors and styles to match the image
        card_width = 2.3 * inch
        card_height = 1.0 * inch  # reduce card height
        row_height = card_height / 2
        # Custom vertical spacing between lines inside card (in points)
        custom_line_spacing = 1  # spacing between value and label
        custom_label_spacing = (
            1  # spacing between label lines (e.g. label and sublabel) - no extra gap
        )

        # Card 1: Total CO₂ Emissions (blue text, light blue bg)
        card1_style = TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), thai_font_bold),
                # Value row font size
                ("FONTSIZE", (0, 0), (0, 0), 14),
                # Label rows font size
                ("FONTSIZE", (0, 1), (0, 2), 9),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
                ("TEXTCOLOR", (0, 0), (0, 0), colors.HexColor("#155DFC")),
                ("TEXTCOLOR", (0, 1), (0, 2), colors.HexColor("#6b7280")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFF6FF")),
                # ('BOX', (0, 0), (-1, -1), 1.2, colors.HexColor('#d1d5db')),  # removed border
                ("TOPPADDING", (0, 0), (-1, -1), 18),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                # Custom vertical spacing between value and label
                # ('BOTTOMPADDING', (0, 0), (0, 1), custom_line_spacing),
                # Custom vertical spacing between label lines
                # ('BOTTOMPADDING', (0, 1), (0, 2), custom_label_spacing),
            ]
        )
        card1 = Table(
            [[f"{data['total_emissions']:,.2f} tonCO₂e"], ["Total CO₂ Emissions"]],
            colWidths=[card_width],
            rowHeights=[row_height, row_height],
        )
        card1.setStyle(card1_style)

        # Card 2: Average Emissions (green text, light green bg)
        card2_style = TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), thai_font_bold),
                # Value row font size
                ("FONTSIZE", (0, 0), (0, 0), 14),
                # Label rows font size
                ("FONTSIZE", (0, 1), (0, 2), 9),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
                ("TEXTCOLOR", (0, 0), (0, 0), colors.HexColor("#36A63E")),
                ("TEXTCOLOR", (0, 1), (0, 2), colors.HexColor("#6b7280")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0FDF4")),
                # ('BOX', (0, 0), (-1, -1), 1.2, colors.HexColor('#d1d5db')),  # removed border
                ("TOPPADDING", (0, 0), (-1, -1), 18),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                # Custom vertical spacing between value and label
                # ('BOTTOMPADDING', (0, 0), (0, 1), custom_line_spacing),
                # Custom vertical spacing between label lines
                # ('BOTTOMPADDING', (0, 1), (0, 2), custom_label_spacing),
            ]
        )
        avg_label = (
            "Per Week" if data["average_label"] == "Per Week" else data["average_label"]
        )
        card2 = Table(
            [
                [f"{data['daily_average']:,.2f} tCO₂e"],
                [f"Average Emissions ({avg_label})"],
            ],
            colWidths=[card_width],
            rowHeights=[row_height, row_height],
        )
        card2.setStyle(card2_style)

        # Card 3: vs Last Year (purple text, light purple bg)
        card3_style = TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), thai_font_bold),
                # Value row font size
                ("FONTSIZE", (0, 0), (0, 0), 14),
                # Label rows font size
                ("FONTSIZE", (0, 1), (0, 2), 9),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
                ("TEXTCOLOR", (0, 0), (0, 0), colors.HexColor("#9810FA")),
                ("TEXTCOLOR", (0, 1), (0, 2), colors.HexColor("#6b7280")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FAF5FF")),
                # ('BOX', (0, 0), (-1, -1), 1.2, colors.HexColor('#d1d5db')),  # removed border
                ("TOPPADDING", (0, 0), (-1, -1), 18),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                # Custom vertical spacing between value and label
                # ('BOTTOMPADDING', (0, 0), (0, 1), custom_line_spacing),
                # Custom vertical spacing between label lines
                # ('BOTTOMPADDING', (0, 1), (0, 2), custom_label_spacing),
            ]
        )
        card3 = Table(
            [
                [f"{data['year_change_percent']:+.1f}%"],
                [
                    f"vs Last Year ({'Increase' if data['year_change_trend']=='increase' else data['year_change_trend'].capitalize()})"
                ],
            ],
            colWidths=[card_width],
            rowHeights=[row_height, row_height],
        )
        card3.setStyle(card3_style)

        # Place cards in a row with spacing between each card
        card_gap = 0.25 * inch  # horizontal gap between cards
        cards_row = Table(
            [[card1, "", card2, "", card3]],
            colWidths=[card_width, card_gap, card_width, card_gap, card_width],
            rowHeights=[card_height],
        )
        cards_row.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    # Make gap columns transparent
                    ("BACKGROUND", (1, 0), (1, 0), colors.white),
                    ("BACKGROUND", (3, 0), (3, 0), colors.white),
                    ("BOX", (1, 0), (1, 0), 0, colors.white),
                    ("BOX", (3, 0), (3, 0), 0, colors.white),
                ]
            )
        )
        story.append(cards_row)
        story.append(Spacer(1, 20))

        # Top Subscopes for Scope 1
        if data.get("scope_data"):
            scope1_subscopes = [
                info for info in data["scope_data"].values() if info["ghg_scope"] == 1
            ]
            scope1_subscopes = sorted(
                scope1_subscopes, key=lambda x: x["emissions"], reverse=True
            )[:3]
            top_subscope_header = [
                "#",
                "Subscope Name",
                "Scope/Subscope",
                "Emissions (tCO₂e)",
            ]
            top_subscope_rows = []
            for idx, subscope in enumerate(scope1_subscopes, 1):
                scope_sub_label = f"{subscope['ghg_scope']}.{subscope['ghg_sup_scope']}"
                subscope_name_para = Paragraph(
                    subscope.get("ghg_name", ""),
                    ParagraphStyle(
                        "SubscopeName",
                        fontName=thai_font_name,
                        fontSize=9,
                        wordWrap="CJK",
                    ),
                )
                top_subscope_rows.append(
                    [
                        str(idx),
                        subscope_name_para,
                        scope_sub_label,
                        f"{subscope['emissions']:.2f}",
                    ]
                )
            top_subscope_table_data = [top_subscope_header] + top_subscope_rows
            # Table width matches cards row: 3*card_width + 2*card_gap
            total_table_width = 3 * card_width + 2 * card_gap
            # Proportional column widths (same ratio as before)
            col_widths = [
                0.5 / 5.1 * total_table_width,
                2.2 / 5.1 * total_table_width,
                1.2 / 5.1 * total_table_width,
                1.2 / 5.1 * total_table_width,
            ]
            top_subscope_table = Table(top_subscope_table_data, colWidths=col_widths)
            top_subscope_table.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, -1), thai_font_name),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        # Header: background = text color, text = white
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#155DFC")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#EFF6FF")),
                        ("ALIGN", (0, 0), (0, -1), "CENTER"),
                        ("ALIGN", (1, 0), (1, -1), "LEFT"),
                        ("ALIGN", (2, 0), (2, -1), "CENTER"),
                        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.append(
                Paragraph(
                    "Top Subscopes for Scope 1",
                    ParagraphStyle(
                        "TopSubscopeTitle",
                        fontName=thai_font_bold,
                        fontSize=13,
                        textColor=colors.HexColor("#155DFC"),
                        spaceAfter=9,
                        alignment=0,
                    ),
                )
            )
            story.append(top_subscope_table)
            story.append(Spacer(1, 16))
        # Top Subscopes for Scope 2
        if data.get("scope_data"):
            scope2_subscopes = [
                info for info in data["scope_data"].values() if info["ghg_scope"] == 2
            ]
            scope2_subscopes = sorted(
                scope2_subscopes, key=lambda x: x["emissions"], reverse=True
            )[:3]
            top_subscope_header2 = [
                "#",
                "Subscope Name",
                "Scope/Subscope",
                "Emissions (tCO₂e)",
            ]
            top_subscope_rows2 = []
            for idx, subscope in enumerate(scope2_subscopes, 1):
                scope_sub_label = f"{subscope['ghg_scope']}.{subscope['ghg_sup_scope']}"
                subscope_name_para2 = Paragraph(
                    subscope.get("ghg_name", ""),
                    ParagraphStyle(
                        "SubscopeName2",
                        fontName=thai_font_name,
                        fontSize=9,
                        wordWrap="CJK",
                    ),
                )
                top_subscope_rows2.append(
                    [
                        str(idx),
                        subscope_name_para2,
                        scope_sub_label,
                        f"{subscope['emissions']:.2f}",
                    ]
                )
            top_subscope_table_data2 = [top_subscope_header2] + top_subscope_rows2
            top_subscope_table2 = Table(top_subscope_table_data2, colWidths=col_widths)
            top_subscope_table2.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, -1), thai_font_name),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        # Header: background = text color, text = white
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#36A63E")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#D1FAE5")),
                        ("ALIGN", (0, 0), (0, -1), "CENTER"),
                        ("ALIGN", (1, 0), (1, -1), "LEFT"),
                        ("ALIGN", (2, 0), (2, -1), "CENTER"),
                        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.append(
                Paragraph(
                    "Top Subscopes for Scope 2",
                    ParagraphStyle(
                        "TopSubscopeTitle2",
                        fontName=thai_font_bold,
                        fontSize=13,
                        textColor=colors.HexColor("#36A63E"),
                        spaceAfter=9,
                        alignment=0,
                    ),
                )
            )
            story.append(top_subscope_table2)
            story.append(Spacer(1, 16))

        # Top Subscopes for Scope 3
        if data.get("scope_data"):
            scope3_subscopes = [
                info for info in data["scope_data"].values() if info["ghg_scope"] == 3
            ]
            scope3_subscopes = sorted(
                scope3_subscopes, key=lambda x: x["emissions"], reverse=True
            )[:3]
            top_subscope_header3 = [
                "#",
                "Subscope Name",
                "Scope/Subscope",
                "Emissions (tCO₂e)",
            ]
            top_subscope_rows3 = []
            for idx, subscope in enumerate(scope3_subscopes, 1):
                scope_sub_label = f"{subscope['ghg_scope']}.{subscope['ghg_sup_scope']}"
                subscope_name_para3 = Paragraph(
                    subscope.get("ghg_name", ""),
                    ParagraphStyle(
                        "SubscopeName3",
                        fontName=thai_font_name,
                        fontSize=9,
                        wordWrap="CJK",
                    ),
                )
                top_subscope_rows3.append(
                    [
                        str(idx),
                        subscope_name_para3,
                        scope_sub_label,
                        f"{subscope['emissions']:.2f}",
                    ]
                )
            top_subscope_table_data3 = [top_subscope_header3] + top_subscope_rows3
            top_subscope_table3 = Table(top_subscope_table_data3, colWidths=col_widths)
            top_subscope_table3.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, -1), thai_font_name),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        # Header: background = text color, text = white
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#9810FA")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F3E8FF")),
                        ("ALIGN", (0, 0), (0, -1), "CENTER"),
                        ("ALIGN", (1, 0), (1, -1), "LEFT"),
                        ("ALIGN", (2, 0), (2, -1), "CENTER"),
                        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.append(
                Paragraph(
                    "Top Subscopes for Scope 3",
                    ParagraphStyle(
                        "TopSubscopeTitle3",
                        fontName=thai_font_bold,
                        fontSize=13,
                        textColor=colors.HexColor("#9810FA"),
                        spaceAfter=9,
                        alignment=0,
                    ),
                )
            )
            story.append(top_subscope_table3)
            story.append(Spacer(1, 16))
        # Monthly tCO₂e Comparison Table (2023 vs 2024)
        # Extract month names and values for current and last year
        month_names_en = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]
        month_names_th = [
            "มกราคม",
            "กุมภาพันธ์",
            "มีนาคม",
            "เมษายน",
            "พฤษภาคม",
            "มิถุนายน",
            "กรกฎาคม",
            "สิงหาคม",
            "กันยายน",
            "ตุลาคม",
            "พฤศจิกายน",
            "ธันวาคม",
        ]
        current_monthly = [data["daily_data"].get(m, 0) for m in month_names_en]
        last_monthly = [last_year_data["daily_data"].get(m, 0) for m in month_names_en]
        # Table header
        compare_header = [
            "เดือน",
            f"{int(selected_year)-1} tCO₂e",
            f"{selected_year} tCO₂e",
        ]
        compare_rows = []
        for i, m_th in enumerate(month_names_th):
            compare_rows.append(
                [m_th, f"{last_monthly[i]:,.2f}", f"{current_monthly[i]:,.2f}"]
            )
        compare_table_data = [compare_header] + compare_rows
        # Table width matches cards row
        total_table_width = 3 * card_width + 2 * card_gap
        col_widths = [
            1.5 / 5.1 * total_table_width,
            1.8 / 5.1 * total_table_width,
            1.8 / 5.1 * total_table_width,
        ]
        compare_table = Table(compare_table_data, colWidths=col_widths)
        compare_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), thai_font_name),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    # Header: background orange, text white
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F54900")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    # Body rows background
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#FFF7ED")),
                    ("ALIGN", (0, 0), (0, -1), "CENTER"),
                    ("ALIGN", (1, 0), (2, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(
            Paragraph(
                "ตารางเปรียบเทียบค่า tCO₂e รายเดือน ({} vs {})".format(
                    int(selected_year) - 1, selected_year
                ),
                ParagraphStyle(
                    "CompareTitle",
                    fontName=thai_font_bold,
                    fontSize=13,
                    textColor=colors.HexColor("#F54900"),
                    spaceAfter=9,
                    alignment=0,
                ),
            )
        )
        story.append(compare_table)
        story.append(Spacer(1, 16))
        # Charts (bar, pie)

        temp_image_paths = []

        def add_base64_image(base64_str, width=5 * inch, height=2 * inch):
            if base64_str:
                tmp_img = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                tmp_img.write(base64.b64decode(base64_str))
                tmp_img.flush()
                tmp_img.close()
                temp_image_paths.append(tmp_img.name)
                img = Image(tmp_img.name, width=width, height=height)
                img.hAlign = "CENTER"
                story.append(img)
                story.append(Spacer(1, 12))

        story.append(Paragraph("Emissions by Month", styles["Heading3"]))
        add_base64_image(bar_chart_base64)
        story.append(Paragraph("Category Breakdown", styles["Heading3"]))
        # Prepare chart image and table for side-by-side layout
        from reportlab.platypus import Table as RLTable, TableStyle as RLTableStyle

        chart_img = None
        temp_img_path = None
        if category_chart_base64:
            import tempfile, base64

            tmp_img = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            tmp_img.write(base64.b64decode(category_chart_base64))
            tmp_img.flush()
            tmp_img.close()
            temp_img_path = tmp_img.name
            chart_img = Image(temp_img_path, width=2.5 * inch, height=2.5 * inch)
            chart_img.hAlign = "CENTER"
        # Category Breakdown Table (Scope, %, tCO2e)
        total_emissions = sum(
            [
                data["category_data"].get(label, 0)
                for label in ["Scope 1", "Scope 2", "Scope 3"]
            ]
        )
        breakdown_table_header = ["Scope", "%", "tCO₂e"]
        breakdown_table_rows = []
        for label, color in zip(
            ["Scope 1", "Scope 2", "Scope 3"], ["#4f46e5", "#10b981", "#f97316"]
        ):
            value = data["category_data"].get(label, 0)
            percent = (value / total_emissions * 100) if total_emissions > 0 else 0
            breakdown_table_rows.append(
                [
                    Paragraph(
                        label,
                        ParagraphStyle(
                            "ScopeLabel",
                            fontName=thai_font_bold,
                            fontSize=10,
                            textColor=colors.HexColor(color),
                        ),
                    ),
                    f"{percent:.1f}%",
                    f"{value:,.2f}",
                ]
            )
        breakdown_table_data = [breakdown_table_header] + breakdown_table_rows
        table_width = 3.5 * inch
        col_widths = [
            1.2 / 4.4 * table_width,
            1.0 / 4.4 * table_width,
            2.2 / 4.4 * table_width,
        ]
        breakdown_table = Table(
            breakdown_table_data,
            colWidths=col_widths,
            rowHeights=[22] + [28] * len(breakdown_table_rows),
        )
        breakdown_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), thai_font_name),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAEAF2")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
                    ("ALIGN", (0, 0), (0, -1), "CENTER"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("ALIGN", (2, 0), (2, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        # Place chart and table in a single row (2 columns)
        # Wrap table in a right-aligned container
        from reportlab.platypus import Spacer

        right_table = RLTable(
            [[Spacer(1, 40)], [breakdown_table], [Spacer(1, 40)]],
            colWidths=[3.5 * inch],
        )
        right_table.setStyle(
            RLTableStyle(
                [
                    ("ALIGN", (0, 1), (0, 1), "RIGHT"),
                    ("VALIGN", (0, 1), (0, 1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        row_table = RLTable(
            [[chart_img, right_table]], colWidths=[2.7 * inch, 3.5 * inch]
        )
        row_table.setStyle(
            RLTableStyle(
                [
                    ("VALIGN", (0, 0), (0, 0), "TOP"),
                    ("VALIGN", (1, 0), (1, 0), "MIDDLE"),
                    ("ALIGN", (0, 0), (0, 0), "CENTER"),
                    ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        story.append(row_table)
        story.append(Spacer(1, 16))

        # Notes
        if notes.strip():
            import urllib.parse

            decoded_notes = urllib.parse.unquote(notes)
            story.append(Spacer(1, 20))
            notes_header = Paragraph(
                "หมายเหตุ",
                ParagraphStyle(
                    "NotesHeader",
                    fontName=thai_font_bold,
                    fontSize=13,
                    textColor=colors.HexColor("#155DFC"),
                    spaceAfter=9,
                    alignment=0,
                ),
            )
            story.append(notes_header)
            notes_para = Paragraph(
                decoded_notes,
                ParagraphStyle(
                    "NotesText",
                    fontName=thai_font_name,
                    fontSize=11,
                    textColor=colors.HexColor("#444"),
                    leading=16,
                ),
            )
            story.append(notes_para)

        doc.build(story)
        pdf_buffer.seek(0)

        # ลบไฟล์ภาพชั่วคราวหลัง doc.build เสร็จ
        if temp_img_path:
            try:
                os.unlink(temp_img_path)
            except Exception:
                pass
        for img_path in temp_image_paths:
            try:
                os.unlink(img_path)
            except Exception:
                pass

        filename = f"summary_report_{selected_year}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )

    except Exception as e:
        return jsonify({"error": f"เกิดข้อผิดพลาดในการสร้างรายงาน: {str(e)}"}), 500


def create_htmx_response(
    template_path, template_vars=None, success_message=None, error_message=None
):
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
        response.headers["HX-Trigger"] = json.dumps(trigger_data)

    return response
