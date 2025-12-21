from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify, make_response
from flask_login import login_required, current_user
from webapp.models.file_model import TemplateExcel, UploadedFile
from webapp.models.materail_model import Material
from webapp.models.campus_and_department_model import CampusAndDepartment
from werkzeug.utils import secure_filename
import io
import json
import urllib.parse
from datetime import datetime

module = Blueprint("template_excel", __name__, url_prefix="/template-excel-management")

ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB (MongoDB limit)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@module.route("/upload-modal", methods=["GET"])
@login_required
def upload_modal():
    """โหลด upload form modal"""
    campuses = CampusAndDepartment.objects.all()
    all_years = sorted(Material.objects.distinct('year'), reverse=True)
    return render_template(
        "template-excel-management/partials/upload-modal.html",
        campuses=campuses,
        years=all_years
    )

@module.route("/edit-name-modal/<template_id>", methods=["GET"])
@login_required
def edit_name_modal(template_id):
    """โหลด edit name form modal"""
    template = TemplateExcel.objects(id=template_id).first()
    if not template:
        return "<p class='text-error'>ไม่พบไฟล์</p>", 404
    return render_template(
        "template-excel-management/partials/edit-name-modal.html",
        template=template
    )

@module.route("/edit-modal/<template_id>", methods=["GET"])
@login_required
def edit_modal(template_id):
    """โหลด edit form modal (แก้ไขทั้งหมด)"""
    template = TemplateExcel.objects(id=template_id).first()
    if not template:
        return "<p class='text-error'>ไม่พบไฟล์</p>", 404
    
    campuses = CampusAndDepartment.objects.all()
    all_years = sorted(Material.objects.distinct('year'), reverse=True)
    
    return render_template(
        "template-excel-management/partials/edit-modal.html",
        template=template,
        campuses=campuses,
        years=all_years
    )

@module.route("/", methods=["GET"])
@login_required
def template_excel_list():
    """แสดงรายการไฟล์ Excel ต้นฉบับทั้งหมด"""
    # ดึง filter parameters
    filter_campus_id = request.args.get('campus_id', '')
    filter_year = request.args.get('year', '')
    filter_search = request.args.get('search', '').strip()
    
    # ดึงข้อมูล campus และปี
    campuses = CampusAndDepartment.objects.all()
    all_years = sorted(Material.objects.distinct('year'), reverse=True)
    
    # Build query
    query_filters = {}
    if filter_campus_id:
        query_filters['campus_id'] = filter_campus_id
    if filter_year:
        query_filters['year'] = int(filter_year)
    
    # ดึงไฟล์ที่อัพโหลดแล้ว
    templates = TemplateExcel.objects(**query_filters).order_by('-year', 'display_name')
    
    # ถ้ามีการค้นหาชื่อ
    if filter_search:
        templates = [t for t in templates if filter_search.lower() in t.display_name.lower()]
    
    return render_template(
        "template-excel-management/template-excel-list.html",
        templates=templates,
        campuses=campuses,
        years=all_years,
        filter_campus_id=filter_campus_id,
        filter_year=filter_year,
        filter_search=filter_search
    )

@module.route("/upload", methods=["POST"])
@login_required
def upload_template_excel():
    """อัพโหลดไฟล์ Excel ต้นฉบับ"""
    try:
        campus_id = request.form.get('campus_id')
        year = request.form.get('year', type=int)
        display_name = request.form.get('display_name', '').strip()
        
        if not campus_id:
            flash("กรุณาเลือกวิทยาเขต", "error")
            return redirect(url_for('template_excel.template_excel_list'))
        
        if not year:
            flash("กรุณาระบุปี", "error")
            return redirect(url_for('template_excel.template_excel_list'))
        
        if not display_name:
            flash("กรุณาระบุชื่อไฟล์", "error")
            return redirect(url_for('template_excel.template_excel_list'))
        
        if 'file' not in request.files:
            flash("กรุณาเลือกไฟล์", "error")
            return redirect(url_for('template_excel.template_excel_list'))
        
        file = request.files['file']
        if file.filename == '':
            flash("กรุณาเลือกไฟล์", "error")
            return redirect(url_for('template_excel.template_excel_list'))
        
        if not allowed_file(file.filename):
            flash("รองรับเฉพาะไฟล์ .xlsx หรือ .xls เท่านั้น", "error")
            return redirect(url_for('template_excel.template_excel_list'))
        
        # อ่านไฟล์
        file_data = file.read()
        
        # ตรวจสอบขนาดไฟล์
        if len(file_data) > MAX_FILE_SIZE:
            flash(f"ไฟล์ใหญ่เกินไป (สูงสุด {MAX_FILE_SIZE / (1024*1024):.0f} MB)", "error")
            return redirect(url_for('template_excel.template_excel_list'))
        
        # สร้าง UploadedFile
        filename = secure_filename(file.filename)
        uploaded_file = UploadedFile(
            filename=filename,
            content_type=file.content_type or 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            data=file_data
        )
        
        # สร้างใหม่
        template = TemplateExcel(
            campus_id=campus_id,
            year=year,
            display_name=display_name,
            file=uploaded_file,
            uploaded_by=str(current_user.id)
        )
        template.save()
        
        # Clear cache ของ get_keys_by_scope_from_excel
        from webapp.web.views.material_mapping_excel_view import get_keys_by_scope_from_excel
        get_keys_by_scope_from_excel.cache_clear()
        
        # ดึงข้อมูลใหม่เพื่อ return table rows
        query_filters = {}
        if campus_id:
            query_filters['campus_id'] = campus_id
        if year:
            query_filters['year'] = year
        
        templates = TemplateExcel.objects(**query_filters).order_by('-year', 'display_name')
        campuses = CampusAndDepartment.objects.all()
        
        response = make_response(render_template(
            "template-excel-management/partials/table-rows.html",
            templates=templates,
            campuses=campuses
        ))
        trigger_data = {"closeModal": True, "showSuccess": f"File '{display_name}' uploaded successfully"}
        response.headers['HX-Trigger'] = json.dumps(trigger_data)
        return response
    
    except Exception as e:
        response = make_response(f"<p class='text-error'>Error: {str(e)}</p>")
        trigger_data = {"showError": f"Upload failed: {str(e)}"}
        response.headers['HX-Trigger'] = json.dumps(trigger_data)
        return response

@module.route("/download/<template_id>", methods=["GET"])
@login_required
def download_template_excel(template_id):
    """ดาวน์โหลดไฟล์ Excel ต้นฉบับ"""
    template = TemplateExcel.objects(id=template_id).first()
    if not template or not template.file:
        flash("ไม่พบไฟล์", "error")
        return redirect(url_for('template_excel.template_excel_list'))
    
    # สร้าง BytesIO จาก binary data
    file_stream = io.BytesIO(template.file.data)
    file_stream.seek(0)
    
    # ใช้ display_name เป็นชื่อไฟล์ โดยเอา extension จากไฟล์ต้นฉบับ
    original_extension = template.file.filename.rsplit('.', 1)[-1] if '.' in template.file.filename else 'xlsx'
    download_filename = f"{template.display_name}.{original_extension}"
    
    return send_file(
        file_stream,
        as_attachment=True,
        download_name=download_filename,
        mimetype=template.file.content_type
    )

@module.route("/delete/<template_id>", methods=["POST", "DELETE"])
@login_required
def delete_template_excel(template_id):
    """ลบไฟล์ Excel ต้นฉบับ"""
    template = TemplateExcel.objects(id=template_id).first()
    if not template:
        response = make_response("<p class='text-error'>File not found</p>")
        trigger_data = {"showError": "File not found"}
        response.headers['HX-Trigger'] = json.dumps(trigger_data)
        return response
    
    display_name = template.display_name
    template.delete()
    
    # Clear cache
    from webapp.web.views.material_mapping_excel_view import get_keys_by_scope_from_excel
    get_keys_by_scope_from_excel.cache_clear()
    
    # Return updated table rows
    templates = TemplateExcel.objects.all().order_by('-year', 'display_name')
    campuses = CampusAndDepartment.objects.all()
    
    response = make_response(render_template(
        "template-excel-management/partials/table-rows.html",
        templates=templates,
        campuses=campuses
    ))
    trigger_data = {"showSuccess": f"File '{display_name}' deleted successfully"}
    response.headers['HX-Trigger'] = json.dumps(trigger_data)
    return response

@module.route("/update-name/<template_id>", methods=["POST"])
@login_required
def update_template_name(template_id):
    """แก้ไขชื่อไฟล์"""
    try:
        template = TemplateExcel.objects(id=template_id).first()
        if not template:
            response = make_response("<p class='text-error'>File not found</p>")
            trigger_data = {"showError": "File not found"}
            response.headers['HX-Trigger'] = json.dumps(trigger_data)
            return response
        
        new_name = request.form.get('display_name', '').strip()
        if not new_name:
            response = make_response("<p class='text-error'>Please enter a name</p>")
            trigger_data = {"showError": "Please enter a name"}
            response.headers['HX-Trigger'] = json.dumps(trigger_data)
            return response
        
        # ใช้ update() แทน save() เพื่อ update เฉพาะ field ที่ต้องการ
        template.update(set__display_name=new_name)
        
        # Return updated table rows
        templates = TemplateExcel.objects.all().order_by('-year', 'display_name')
        campuses = CampusAndDepartment.objects.all()
        
        response = make_response(render_template(
            "template-excel-management/partials/table-rows.html",
            templates=templates,
            campuses=campuses
        ))
        trigger_data = {"closeModal": True, "showSuccess": "File name updated successfully"}
        response.headers['HX-Trigger'] = json.dumps(trigger_data)
        return response
    except Exception as e:
        response = make_response(f"<p class='text-error'>Error: {str(e)}</p>")
        trigger_data = {"showError": f"Update failed: {str(e)}"}
        response.headers['HX-Trigger'] = json.dumps(trigger_data)
        return response

@module.route("/update-template/<template_id>", methods=["POST"])
@login_required
def update_template(template_id):
    """แก้ไขข้อมูลไฟล์ทั้งหมด (campus, year, display_name)"""
    try:
        template = TemplateExcel.objects(id=template_id).first()
        if not template:
            response = make_response("<p class='text-error'>File not found</p>")
            trigger_data = {"showError": "File not found"}
            response.headers['HX-Trigger'] = json.dumps(trigger_data)
            return response
        
        # รับข้อมูลจาก form
        campus_id = request.form.get('campus_id', '').strip()
        year = request.form.get('year', type=int)
        display_name = request.form.get('display_name', '').strip()
        
        # Validation
        if not campus_id:
            response = make_response("<p class='text-error'>Please select campus</p>")
            trigger_data = {"showError": "Please select campus"}
            response.headers['HX-Trigger'] = json.dumps(trigger_data)
            return response
            
        if not year:
            response = make_response("<p class='text-error'>Please select year</p>")
            trigger_data = {"showError": "Please select year"}
            response.headers['HX-Trigger'] = json.dumps(trigger_data)
            return response
            
        if not display_name:
            response = make_response("<p class='text-error'>Please enter display name</p>")
            trigger_data = {"showError": "Please enter display name"}
            response.headers['HX-Trigger'] = json.dumps(trigger_data)
            return response
        
        # Update ทั้งหมด
        template.update(
            set__campus_id=campus_id,
            set__year=year,
            set__display_name=display_name
        )
        
        # Return updated table rows
        templates = TemplateExcel.objects.all().order_by('-year', 'display_name')
        campuses = CampusAndDepartment.objects.all()
        
        response = make_response(render_template(
            "template-excel-management/partials/table-rows.html",
            templates=templates,
            campuses=campuses
        ))
        trigger_data = {"closeModal": True, "showSuccess": "Template updated successfully"}
        response.headers['HX-Trigger'] = json.dumps(trigger_data)
        return response
    except Exception as e:
        response = make_response(f"<p class='text-error'>Error: {str(e)}</p>")
        trigger_data = {"showError": f"Update failed: {str(e)}"}
        response.headers['HX-Trigger'] = json.dumps(trigger_data)
        return response

@module.route("/table-rows", methods=["GET"])
@login_required
def template_excel_table_rows():
    """HTMX endpoint สำหรับ reload ตาราง"""
    filter_campus_id = request.args.get('campus_id', '')
    filter_year = request.args.get('year', '')
    filter_search = request.args.get('search', '').strip()
    
    # Build query
    query_filters = {}
    if filter_campus_id:
        query_filters['campus_id'] = filter_campus_id
    if filter_year:
        query_filters['year'] = int(filter_year)
    
    templates = TemplateExcel.objects(**query_filters).order_by('-year', 'display_name')
    
    if filter_search:
        templates = [t for t in templates if filter_search.lower() in t.display_name.lower()]
    
    campuses = CampusAndDepartment.objects.all()
    
    return render_template(
        "template-excel-management/partials/table-rows.html",
        templates=templates,
        campuses=campuses
    )
