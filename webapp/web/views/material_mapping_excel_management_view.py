from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from ...models import CampusAndDepartment, MaterialMappingExcel, Material

module = Blueprint("material_mapping_excel_management", __name__, url_prefix="/material-mapping-excel-admin")

@module.route("/table-rows", methods=["GET"])
@login_required
def material_mapping_excel_management_table_rows():
    filter_campus_id = request.args.get('campus_id')
    filter_department_search = request.args.get('department_search', '').strip()
    filter_year = request.args.get('year', '2025')
    
    campuses = CampusAndDepartment.objects.all()
    
    query_filters = {}
    if filter_year:
        query_filters['year'] = int(filter_year)
    if filter_campus_id:
        query_filters['campus_id'] = filter_campus_id
    
    mappings = MaterialMappingExcel.objects(**query_filters)
    
    from webapp.models.file_model import TemplateExcel
    template_query = {'year': int(filter_year)} if filter_year else {}
    if filter_campus_id:
        template_query['campus_id'] = filter_campus_id
    templates = TemplateExcel.objects(**template_query).order_by('display_name')
    
    rendered_rows = render_template(
        "material-mapping-excel-management/partials/table-rows.html",
        campuses=campuses,
        mappings=mappings,
        templates=templates,
        filter_campus_id=filter_campus_id,
        filter_department_search=filter_department_search,
        filter_year=filter_year
    )
    return rendered_rows

@module.route("/", methods=["GET"])
@login_required
def admin_mapping_excel_view():
    years = sorted(Material.objects.distinct('year'), reverse=True)
    filter_campus_id = request.args.get('campus_id')
    filter_year = request.args.get('year', str(years[0]) if years else '')
    campuses = CampusAndDepartment.objects.all()
    mappings = MaterialMappingExcel.objects(year=int(filter_year)) if filter_year else MaterialMappingExcel.objects()
    
    # Get template excel files
    from webapp.models.file_model import TemplateExcel
    template_query = {'year': int(filter_year)} if filter_year else {}
    if filter_campus_id:
        template_query['campus_id'] = filter_campus_id
    templates = TemplateExcel.objects(**template_query).order_by('display_name')
    
    return render_template(
        "material-mapping-excel-management/admin-mapping-excel-view.html",
        campuses=campuses,
        mappings=mappings,
        templates=templates,
        years=years,
        filter_year=filter_year
    )

@module.route("/api/campus/<campus_id>/departments", methods=["GET"])
@login_required
def get_campus_departments(campus_id):
    try:
        campus = CampusAndDepartment.objects(id=campus_id).first()
        if not campus:
            return jsonify([]), 404
        
        departments = [{"key": dept_key, "name": dept_name} for dept_key, dept_name in campus.department.items()]
        return jsonify(sorted(departments, key=lambda x: x['name']))
    except Exception as e:
        print(f"Error getting departments: {e}")
        return jsonify([]), 500

@module.route("/select-template", methods=["POST"])
@login_required
def select_template():
    try:
        campus_id = request.form.get('campus_id')
        department_key = request.form.get('department_key')
        year = request.form.get('year', type=int)
        template_excel_id = request.form.get('template_excel_id')
        
        if not campus_id or not department_key or not year or not template_excel_id:
            return jsonify({"success": False, "message": "Missing required fields"}), 400
        
        mapping = MaterialMappingExcel.objects(
            campus_id=campus_id,
            department_key=department_key,
            year=year,
            sheet_name="Fr-04.1"
        ).first()
        
        if not mapping:
            mapping = MaterialMappingExcel(
                campus_id=campus_id,
                department_key=department_key,
                year=year,
                sheet_name="Fr-04.1",
                mappings={},
                template_excel_id=template_excel_id
            )
            mapping.save()
        else:
            mapping.update(set__template_excel_id=template_excel_id)
        
        return jsonify({"success": True, "message": "Template selected successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
