from flask import Blueprint, render_template
from flask_login import login_required, logout_user, current_user
from ...models import Scope, CampusAndDepartment, Material
from datetime import datetime
from collections import defaultdict

module = Blueprint("index", __name__)


@module.route("/")
@login_required
def index():
    user = current_user
    
    # Get user's campus and department info
    campus_name = CampusAndDepartment.get_campus_name(user.campus_id)
    department_name = CampusAndDepartment.get_department_name(user.campus_id, user.department_key)
    
    # Get current year
    current_year = datetime.now().year
    
    # Calculate scope progress for user's department
    scopes = Scope.objects(campus=user.campus_id, department=user.department_key)
    total_scopes = scopes.count()
    completed_scopes = 0
    in_progress_scopes = 0
    
    # Count materials and calculate emissions
    total_materials = 0
    total_emissions = 0
    scope_emissions = {1: 0, 2: 0, 3: 0}
    
    # Get all materials for the department
    all_materials = Material.objects(
        campus=user.campus_id,
        department=user.department_key,
        year=current_year
    )
    
    total_materials = all_materials.count()
    
    # Calculate emissions from all materials
    for material in all_materials:
        material_scope = material.scope  # 1, 2, or 3
        if material.result:
            try:
                result_value = float(material.result)
                total_emissions += result_value
                if material_scope in scope_emissions:
                    scope_emissions[material_scope] += result_value
            except (ValueError, TypeError):
                pass
        if material.result2:
            try:
                result2_value = float(material.result2)
                total_emissions += result2_value
                if material_scope in scope_emissions:
                    scope_emissions[material_scope] += result2_value
            except (ValueError, TypeError):
                pass
    
    # Check scope completion status
    for scope in scopes:
        # Get materials for this scope
        materials = Material.objects(
            campus=user.campus_id,
            department=user.department_key,
            scope=scope.ghg_scope,
            sub_scope=scope.ghg_sup_scope,
            year=current_year
        )
        
        material_count = materials.count()
        
        # Check if scope has data
        has_data = False
        for material in materials:
            if material.result or material.result2:
                has_data = True
                break
        
        if material_count > 0 and has_data:
            completed_scopes += 1
        elif material_count > 0:
            in_progress_scopes += 1
    
    not_started_scopes = total_scopes - completed_scopes - in_progress_scopes
    progress_percentage = (completed_scopes / total_scopes * 100) if total_scopes > 0 else 0
    
    # Get recent activity (last 30 days)
    thirty_days_ago = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    recent_updates = Material.objects(
        campus=user.campus_id,
        department=user.department_key,
        update_date__gte=thirty_days_ago
    ).count()
    
    context = {
        "user": user,
        "campus_name": campus_name,
        "department_name": department_name,
        "current_year": current_year,
        "total_scopes": total_scopes,
        "completed_scopes": completed_scopes,
        "in_progress_scopes": in_progress_scopes,
        "not_started_scopes": not_started_scopes,
        "progress_percentage": round(progress_percentage, 1),
        "total_materials": total_materials,
        "total_emissions": round(total_emissions, 2),
        "scope_1_emissions": round(scope_emissions[1], 2),
        "scope_2_emissions": round(scope_emissions[2], 2),
        "scope_3_emissions": round(scope_emissions[3], 2),
        "recent_updates": recent_updates,
    }
    
    return render_template("/index/index.html", **context)
