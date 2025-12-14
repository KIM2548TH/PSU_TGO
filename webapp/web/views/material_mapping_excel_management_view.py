
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, send_file
from flask_login import login_required, current_user
from ...models import CampusAndDepartment, MaterialMappingExcel, User, Material
from ..forms.material_mapping_excel_form import MaterialMappingExcelForm
from webapp.services.export_excel_service import export_material_mapping_excel_to_download

module = Blueprint("material_mapping_excel_management", __name__, url_prefix="/material-mapping-excel-admin")

@module.route("/table-rows", methods=["GET"])
@login_required
def material_mapping_excel_management_table_rows():
    filter_campus_id = request.args.get('campus_id')
    filter_year = request.args.get('year', '2025')
    campuses = CampusAndDepartment.objects.all()
    mappings = MaterialMappingExcel.objects(year=2025)
    rendered_rows = render_template(
        "material-mapping-excel-management/partials/table-rows.html",
        campuses=campuses,
        mappings=mappings,
        filter_campus_id=filter_campus_id,
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
