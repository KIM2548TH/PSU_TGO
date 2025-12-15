
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, send_file, jsonify
from flask_login import login_required, current_user
from ...models import CampusAndDepartment, MaterialMappingExcel, User, Material
from ..forms.material_mapping_excel_form import MaterialMappingExcelForm
from webapp.services.export_excel_service import export_material_mapping_excel_to_download

module = Blueprint("material_mapping_excel_management", __name__, url_prefix="/material-mapping-excel-admin")

@module.route("/table-rows", methods=["GET"])
@login_required
def material_mapping_excel_management_table_rows():
    filter_campus_id = request.args.get('campus_id')
    filter_department_search = request.args.get('department_search', '').strip()
    filter_year = request.args.get('year', '2025')
    
    campuses = CampusAndDepartment.objects.all()
    
    # Build query filters
    query_filters = {}
    if filter_year:
        query_filters['year'] = int(filter_year)
    if filter_campus_id:
        query_filters['campus_id'] = filter_campus_id
    
    # Get all mappings with basic filters
    mappings = MaterialMappingExcel.objects(**query_filters)
    
    # If department search is provided, filter by department name
    if filter_department_search:
        filtered_mappings = []
        for mapping in mappings:
            # Get department name from campus
            campus = next((c for c in campuses if str(c.id) == mapping.campus_id), None)
            if campus and mapping.department_key in campus.department:
                dept_name = campus.department[mapping.department_key]
                # Case-insensitive search
                if filter_department_search.lower() in dept_name.lower():
                    filtered_mappings.append(mapping)
        mappings = filtered_mappings
    
    rendered_rows = render_template(
        "material-mapping-excel-management/partials/table-rows.html",
        campuses=campuses,
        mappings=mappings,
        filter_campus_id=filter_campus_id,
        filter_department_search=filter_department_search,
        filter_year=filter_year
    )
    return rendered_rows

@module.route("/", methods=["GET"])
@login_required
# Only super admin can access
def admin_mapping_excel_view():

    years = sorted(Material.objects.distinct('year'), reverse=True)
    filter_campus_id = request.args.get('campus_id')
    filter_year = request.args.get('year', str(years[0]) if years else '')
    campuses = CampusAndDepartment.objects.all()
    mappings = MaterialMappingExcel.objects(year=int(filter_year)) if filter_year else MaterialMappingExcel.objects()
    return render_template(
        "material-mapping-excel-management/admin-mapping-excel-view.html",
        campuses=campuses,
        mappings=mappings,
        years=years
    )

@module.route("/api/campus/<campus_id>/departments", methods=["GET"])
@login_required
def get_campus_departments(campus_id):
    """API endpoint to get departments for a specific campus"""
    try:
        campus = CampusAndDepartment.objects(id=campus_id).first()
        if not campus:
            return jsonify([]), 404
        
        departments = []
        for dept_key, dept_name in campus.department.items():
            departments.append({
                'key': dept_key,
                'name': dept_name
            })
        
        # Sort by name
        departments.sort(key=lambda x: x['name'])
        
        return jsonify(departments)
    except Exception as e:
        print(f"Error getting departments: {e}")
        return jsonify([]), 500
