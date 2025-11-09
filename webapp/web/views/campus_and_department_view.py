from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, abort, make_response
from flask_login import login_required, current_user
from ...models.campus_and_department_model import CampusAndDepartment
from ..forms.campus_form import CampusForm, DepartmentForm
from ..utils.acl import permissions_required_all
import datetime
import json
import urllib.parse

module = Blueprint("campus_department", __name__, url_prefix="/campus-department")


def create_htmx_response(template_path, template_vars=None, success_message=None, error_message=None, warning_message=None):
    """Helper function สำหรับสร้าง HTMX response พร้อม toast notification"""
    if template_vars is None:
        template_vars = {}
    
    response = make_response(render_template(template_path, **template_vars))
    
    trigger_data = {}
    if success_message:
        trigger_data["showSuccess"] = urllib.parse.quote(success_message)
    if error_message:
        trigger_data["showError"] = urllib.parse.quote(error_message)
    if warning_message:
        trigger_data["showWarning"] = urllib.parse.quote(warning_message)
    
    if trigger_data:
        response.headers['HX-Trigger'] = json.dumps(trigger_data)
    
    return response


@module.route("/", methods=["GET"])
@login_required
@permissions_required_all(["เข้าถึงหน้าจัดการวิทยาเขตและหน่วยงาน"])
def index():
    """แสดงหน้า management campus และ department"""
    campuses = CampusAndDepartment.objects
    return render_template(
        "campus-and-department/campus-and-department-management.html",
        campuses=campuses
    )


@module.route("/add-campus", methods=["GET", "POST"])
@login_required
@permissions_required_all(["เพิ่มวิทยาเขตใหม่"])
def add_campus():
    """เพิ่มวิทยาเขตใหม่"""
    form = CampusForm()
    
    if form.validate_on_submit():
        try:
            # ใช้ Model method แทน
            new_campus = CampusAndDepartment.create_campus(
                form.campus_name.data, 
                form.description.data
            )
            
            # สำหรับ HTMX: ส่งข้อมูลใหม่กลับไปพร้อม toast notification
            campuses = CampusAndDepartment.objects
            return create_htmx_response(
                "campus-and-department/partials/campus-list.html",
                {"campuses": campuses},
                success_message=f"เพิ่มวิทยาเขต '{form.campus_name.data}' สำเร็จ!"
            )
            
        except ValueError as e:
            return create_htmx_response(
                "campus-and-department/partials/add-campus-modal.html",
                {"form": form},
                error_message=str(e)
            )
            
        except Exception as e:
            return create_htmx_response(
                "campus-and-department/partials/add-campus-modal.html",
                {"form": form},
                error_message=f"เกิดข้อผิดพลาด: {str(e)}"
            )
    
    # แสดง validation errors ของ form ผ่าน toast
    if form.errors:
        error_messages = []
        for field, errors in form.errors.items():
            for error in errors:
                error_messages.append(error)
        
        return create_htmx_response(
            "campus-and-department/partials/add-campus-modal.html",
            {"form": form},
            error_message=" | ".join(error_messages)
        )
    
    # GET request: ส่ง modal fragment
    return render_template("campus-and-department/partials/add-campus-modal.html", form=form)


@module.route("/edit-campus/<campus_id>", methods=["GET", "POST"])
@login_required
@permissions_required_all(["แก้ไขวิทยาเขต"])
def edit_campus(campus_id):
    """แก้ไขวิทยาเขต"""
    campus = CampusAndDepartment.objects(id=campus_id).first()
    if not campus:
        abort(404)
    form = CampusForm()
    
    if form.validate_on_submit():
        try:
            # ใช้ Model method แทน
            campus.update_campus_name(
                form.campus_name.data,
                form.description.data
            )
            
            # สำหรับ HTMX: ส่งข้อมูลใหม่กลับไปพร้อม toast notification
            campuses = CampusAndDepartment.objects
            return create_htmx_response(
                "campus-and-department/partials/campus-list.html",
                {"campuses": campuses},
                success_message=f"แก้ไขวิทยาเขต '{form.campus_name.data}' สำเร็จ!"
            )
            
        except ValueError as e:
            return create_htmx_response(
                "campus-and-department/partials/edit-campus-modal.html",
                {"form": form, "campus": campus, "can_delete": campus.can_delete_campus()},
                error_message=str(e)
            )
            
        except Exception as e:
            return create_htmx_response(
                "campus-and-department/partials/edit-campus-modal.html",
                {"form": form, "campus": campus, "can_delete": campus.can_delete_campus()},
                error_message=f"เกิดข้อผิดพลาด: {str(e)}"
            )
    
    # แสดง validation errors ของ form ผ่าน toast
    if form.errors:
        error_messages = []
        for field, errors in form.errors.items():
            for error in errors:
                error_messages.append(error)
        
        return create_htmx_response(
            "campus-and-department/partials/edit-campus-modal.html",
            {"form": form, "campus": campus, "can_delete": campus.can_delete_campus()},
            error_message=" | ".join(error_messages)
        )
    
    # ถ้าเป็น GET request ให้ populate form ด้วยข้อมูลเดิม
    if request.method == "GET":
        form.campus_name.data = campus.name.get("0", "")
        form.description.data = campus.description or ""
    
    # ตรวจสอบว่าวิทยาเขตสามารถลบได้หรือไม่
    can_delete = campus.can_delete_campus()
    
    return render_template("campus-and-department/partials/edit-campus-modal.html", 
                         form=form, campus=campus, can_delete=can_delete)


@module.route("/add-department/<campus_id>", methods=["GET", "POST"])
@login_required
@permissions_required_all(["เพิ่มหน่วยงานในวิทยาเขต"])
def add_department(campus_id):
    """เพิ่มหน่วยงานในวิทยาเขต"""
    campus = CampusAndDepartment.objects(id=campus_id).first()
    if not campus:
        abort(404)
    form = DepartmentForm()
    
    if form.validate_on_submit():
        try:
            # เพิ่ม department ใหม่ และ copy scope จาก 'base' อัตโนมัติ
            campus.add_department(form.department_name.data)
            
            # สำหรับ HTMX: ส่งข้อมูลใหม่กลับไปพร้อม toast notification
            campuses = CampusAndDepartment.objects
            return create_htmx_response(
                "campus-and-department/partials/campus-list.html",
                {"campuses": campuses},
                success_message=f"เพิ่มหน่วยงาน '{form.department_name.data}' สำเร็จ!"
            )
            
        except Exception as e:
            return create_htmx_response(
                "campus-and-department/partials/add-department-modal.html",
                {"form": form, "campus": campus},
                error_message=f"เกิดข้อผิดพลาด: {str(e)}"
            )
    
    # แสดง validation errors ของ form ผ่าน toast
    if form.errors:
        error_messages = []
        for field, errors in form.errors.items():
            for error in errors:
                error_messages.append(error)
        
        return create_htmx_response(
            "campus-and-department/partials/add-department-modal.html",
            {"form": form, "campus": campus},
            error_message=" | ".join(error_messages)
        )
    
    return render_template("campus-and-department/partials/add-department-modal.html", form=form, campus=campus)


@module.route("/edit-department/<campus_id>/<dept_key>", methods=["GET", "POST"])
@login_required
@permissions_required_all(["แก้ไขหน่วยงาน"])
def edit_department(campus_id, dept_key):
    """แก้ไขหน่วยงาน"""
    campus = CampusAndDepartment.objects(id=campus_id).first()
    if not campus:
        abort(404)
    
    if dept_key not in campus.departments:
        # ส่ง error toast และแสดงข้อมูลใหม่
        campuses = CampusAndDepartment.objects
        return create_htmx_response(
            "campus-and-department/partials/campus-list.html",
            {"campuses": campuses},
            error_message="ไม่พบหน่วยงานนี้"
        )
    
    form = DepartmentForm()
    
    if form.validate_on_submit():
        try:
            # ใช้ Model method แทน
            campus.update_department(dept_key, form.department_name.data)
            
            # สำหรับ HTMX: ส่งข้อมูลใหม่กลับไปพร้อม toast notification
            campuses = CampusAndDepartment.objects
            return create_htmx_response(
                "campus-and-department/partials/campus-list.html",
                {"campuses": campuses},
                success_message=f"แก้ไขหน่วยงาน '{form.department_name.data}' สำเร็จ!"
            )
            
        except ValueError as e:
            department = {"key": dept_key, "name": campus.departments[dept_key]}
            dept_name_to_check = form.department_name.data or campus.departments[dept_key]
            can_delete = campus.can_delete_department_by_name(campus.name.get("0", ""), dept_name_to_check)
            
            return create_htmx_response(
                "campus-and-department/partials/edit-department-modal.html",
                {"form": form, "campus": campus, "department": department, "can_delete": can_delete},
                error_message=str(e)
            )
            
        except Exception as e:
            department = {"key": dept_key, "name": campus.departments[dept_key]}
            dept_name_to_check = form.department_name.data or campus.departments[dept_key]
            can_delete = campus.can_delete_department_by_name(campus.name.get("0", ""), dept_name_to_check)
            
            return create_htmx_response(
                "campus-and-department/partials/edit-department-modal.html",
                {"form": form, "campus": campus, "department": department, "can_delete": can_delete},
                error_message=f"เกิดข้อผิดพลาด: {str(e)}"
            )
    
    # แสดง validation errors ของ form ผ่าน toast
    if form.errors:
        error_messages = []
        for field, errors in form.errors.items():
            for error in errors:
                error_messages.append(error)
        
        department = {"key": dept_key, "name": campus.departments[dept_key]}
        dept_name_to_check = form.department_name.data or campus.departments[dept_key]
        can_delete = campus.can_delete_department_by_name(campus.name.get("0", ""), dept_name_to_check)
        
        return create_htmx_response(
            "campus-and-department/partials/edit-department-modal.html",
            {"form": form, "campus": campus, "department": department, "can_delete": can_delete},
            error_message=" | ".join(error_messages)
        )
    
    # ถ้าเป็น GET request ให้ populate form ด้วยข้อมูลเดิม
    if request.method == "GET":
        form.department_name.data = campus.departments[dept_key]
    
    # ตรวจสอบว่าหน่วยงานสามารถลบได้หรือไม่
    dept_name_to_check = form.department_name.data or campus.departments[dept_key]
    can_delete = campus.can_delete_department_by_name(campus.name.get("0", ""), dept_name_to_check)
    
    department = {"key": dept_key, "name": campus.departments[dept_key]}
    return render_template("campus-and-department/partials/edit-department-modal.html", 
                         form=form, campus=campus, department=department, can_delete=can_delete)


@module.route("/delete-campus/<campus_id>", methods=["GET", "POST"])
@login_required
@permissions_required_all(["ลบวิทยาเขต"])
def delete_campus(campus_id):
    """ลบวิทยาเขต"""
    campus = CampusAndDepartment.objects(id=campus_id).first()
    if not campus:
        abort(404)
    
    if request.method == "POST":
        try:
            campus_name = campus.name.get("0", "")
            # ใช้ Model method แทน
            campus.safe_delete()
            
            # สำหรับ HTMX: ส่งข้อมูลใหม่กลับไปพร้อม toast notification สีเหลือง
            campuses = CampusAndDepartment.objects
            return create_htmx_response(
                "campus-and-department/partials/campus-list.html",
                {"campuses": campuses},
                warning_message=f"ลบวิทยาเขต '{campus_name}' เรียบร้อยแล้ว (1 รายการ)"
            )
            
        except ValueError as e:
            campuses = CampusAndDepartment.objects
            return create_htmx_response(
                "campus-and-department/partials/campus-list.html",
                {"campuses": campuses},
                error_message=str(e)
            )
            
        except Exception as e:
            campuses = CampusAndDepartment.objects
            return create_htmx_response(
                "campus-and-department/partials/campus-list.html",
                {"campuses": campuses},
                error_message=f"เกิดข้อผิดพลาด: {str(e)}"
            )
    
    # GET request - redirect กลับไปหน้าหลัก
    return redirect(url_for("campus_department.index"))


@module.route("/delete-department/<campus_id>/<dept_key>", methods=["GET", "POST"])
@login_required
@permissions_required_all(["ลบหน่วยงาน"])
def delete_department(campus_id, dept_key):
    """ลบหน่วยงาน"""
    campus = CampusAndDepartment.objects(id=campus_id).first()
    if not campus:
        abort(404)
    
    if dept_key not in campus.departments:
        # ส่ง error toast
        campuses = CampusAndDepartment.objects
        return create_htmx_response(
            "campus-and-department/partials/campus-list.html",
            {"campuses": campuses},
            error_message="ไม่พบหน่วยงานนี้"
        )
    
    if request.method == "POST":
        try:
            dept_name = campus.departments[dept_key]
            # ใช้ Model method แทน
            campus.delete_department(dept_key)
            
            # สำหรับ HTMX: ส่งข้อมูลใหม่กลับไปพร้อม toast notification สีเหลือง
            campuses = CampusAndDepartment.objects
            return create_htmx_response(
                "campus-and-department/partials/campus-list.html",
                {"campuses": campuses},
                warning_message=f"ลบหน่วยงาน '{dept_name}' เรียบร้อยแล้ว (1 รายการ)"
            )
            
        except ValueError as e:
            campuses = CampusAndDepartment.objects
            return create_htmx_response(
                "campus-and-department/partials/campus-list.html",
                {"campuses": campuses},
                error_message=str(e)
            )
            
        except Exception as e:
            campuses = CampusAndDepartment.objects
            return create_htmx_response(
                "campus-and-department/partials/campus-list.html",
                {"campuses": campuses},
                error_message=f"เกิดข้อผิดพลาด: {str(e)}"
            )
    
    # GET request - redirect กลับไปหน้าหลัก
    return redirect(url_for("campus_department.index"))
