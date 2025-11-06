from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from ...models.campus_and_department_model import CampusAndDepartment
from ..forms.campus_form import CampusForm, DepartmentForm
import datetime

module = Blueprint("campus_department", __name__, url_prefix="/campus-department")


@module.route("/", methods=["GET"])
@login_required
def index():
    """แสดงหน้า management campus และ department"""
    campuses = CampusAndDepartment.objects
    return render_template(
        "campus-and-department/campus-and-department-management.html",
        campuses=campuses
    )


@module.route("/add-campus", methods=["GET", "POST"])
@login_required
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
            
            flash("เพิ่มวิทยาเขตสำเร็จ", "success")
            # สำหรับ HTMX: ส่งข้อมูลใหม่กลับไป
            campuses = CampusAndDepartment.objects
            return render_template("campus-and-department/partials/campus-list.html", campuses=campuses)
            
        except ValueError as e:
            flash(str(e), "error")
            return render_template("campus-and-department/partials/add-campus-modal.html", form=form)
        except Exception as e:
            flash(f"เกิดข้อผิดพลาด: {str(e)}", "error")
    
    # แสดง validation errors ของ form
    if form.errors:
        for field, errors in form.errors.items():
            for error in errors:
                flash(error, "error")
    
    # GET request: ส่ง modal fragment
    return render_template("campus-and-department/partials/add-campus-modal.html", form=form)


@module.route("/edit-campus/<campus_id>", methods=["GET", "POST"])
@login_required
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
            
            flash("แก้ไขวิทยาเขตสำเร็จ", "success")
            # สำหรับ HTMX: ส่งข้อมูลใหม่กลับไป
            campuses = CampusAndDepartment.objects
            return render_template("campus-and-department/partials/campus-list.html", campuses=campuses)
            
        except ValueError as e:
            flash(str(e), "error")
            return render_template("campus-and-department/partials/edit-campus-modal.html", 
                                 form=form, campus=campus, can_delete=campus.can_delete_campus())
        except Exception as e:
            flash(f"เกิดข้อผิดพลาด: {str(e)}", "error")
    
    # แสดง validation errors ของ form
    if form.errors:
        for field, errors in form.errors.items():
            for error in errors:
                flash(error, "error")
    
    # ถ้าเป็น GET request หรือมี validation error ให้ populate form ด้วยข้อมูลเดิม
    if request.method == "GET":
        form.campus_name.data = campus.name.get("0", "")
        form.description.data = campus.description or ""
    
    # ตรวจสอบว่าวิทยาเขตสามารถลบได้หรือไม่
    can_delete = campus.can_delete_campus()
    
    return render_template("campus-and-department/partials/edit-campus-modal.html", 
                         form=form, campus=campus, can_delete=can_delete)


@module.route("/add-department/<campus_id>", methods=["GET", "POST"])
@login_required
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
            
            flash("เพิ่มหน่วยงานสำเร็จ", "success")
            # สำหรับ HTMX: ส่งข้อมูลใหม่กลับไป
            campuses = CampusAndDepartment.objects
            return render_template("campus-and-department/partials/campus-list.html", campuses=campuses)
            
        except Exception as e:
            flash(f"เกิดข้อผิดพลาด: {str(e)}", "error")
    
    # แสดง validation errors ของ form
    if form.errors:
        for field, errors in form.errors.items():
            for error in errors:
                flash(error, "error")
    
    return render_template("campus-and-department/partials/add-department-modal.html", form=form, campus=campus)


@module.route("/edit-department/<campus_id>/<dept_key>", methods=["GET", "POST"])
@login_required
def edit_department(campus_id, dept_key):
    """แก้ไขหน่วยงาน"""
    campus = CampusAndDepartment.objects(id=campus_id).first()
    if not campus:
        abort(404)
    
    if dept_key not in campus.departments:
        flash("ไม่พบหน่วยงานนี้", "error")
        campuses = CampusAndDepartment.objects
        return render_template("campus-and-department/partials/campus-list.html", campuses=campuses)
    
    form = DepartmentForm()
    
    if form.validate_on_submit():
        try:
            # ใช้ Model method แทน
            campus.update_department(dept_key, form.department_name.data)
            
            flash("แก้ไขหน่วยงานสำเร็จ", "success")
            # สำหรับ HTMX: ส่งข้อมูลใหม่กลับไป
            campuses = CampusAndDepartment.objects
            return render_template("campus-and-department/partials/campus-list.html", campuses=campuses)
            
        except ValueError as e:
            flash(str(e), "error")
        except Exception as e:
            flash(f"เกิดข้อผิดพลาด: {str(e)}", "error")
    
    # แสดง validation errors ของ form
    if form.errors:
        for field, errors in form.errors.items():
            for error in errors:
                flash(error, "error")
    
    # ถ้าเป็น GET request ให้ populate form ด้วยข้อมูลเดิม
    if request.method == "GET":
        form.department_name.data = campus.departments[dept_key]
    
    # ตรวจสอบว่าหน่วยงานสามารถลบได้หรือไม่
    # ใช้ชื่อจาก form (ถ้ามีการกรอก) หรือชื่อเดิม (ถ้าเป็น GET request)
    dept_name_to_check = form.department_name.data or campus.departments[dept_key]
    can_delete = campus.can_delete_department_by_name(campus.name.get("0", ""), dept_name_to_check)
    
    department = {"key": dept_key, "name": campus.departments[dept_key]}
    return render_template("campus-and-department/partials/edit-department-modal.html", 
                         form=form, campus=campus, department=department, can_delete=can_delete)


@module.route("/delete-campus/<campus_id>", methods=["GET", "POST"])
@login_required
def delete_campus(campus_id):
    """ลบวิทยาเขต"""
    campus = CampusAndDepartment.objects(id=campus_id).first()
    if not campus:
        abort(404)
    
    if request.method == "POST":
        try:
            # ใช้ Model method แทน
            campus.safe_delete()
            flash("ลบวิทยาเขตสำเร็จ", "success")
            
        except ValueError as e:
            flash(str(e), "error")
        except Exception as e:
            flash(f"เกิดข้อผิดพลาด: {str(e)}", "error")
        
        # สำหรับ HTMX: ส่งข้อมูลใหม่กลับไป
        campuses = CampusAndDepartment.objects
        return render_template("campus-and-department/partials/campus-list.html", campuses=campuses)
    
    # GET request - ไม่ต้องแสดง confirmation modal แล้ว เพราะใช้ในหน้าแก้ไข
    flash("ไม่รองรับการเข้าถึงหน้านี้โดยตรง", "error")
    return redirect(url_for("campus_department.index"))


@module.route("/delete-department/<campus_id>/<dept_key>", methods=["GET", "POST"])
@login_required
def delete_department(campus_id, dept_key):
    """ลบหน่วยงาน"""
    campus = CampusAndDepartment.objects(id=campus_id).first()
    if not campus:
        abort(404)
    
    if dept_key not in campus.departments:
        flash("ไม่พบหน่วยงานนี้", "error")
        campuses = CampusAndDepartment.objects
        return render_template("campus-and-department/partials/campus-list.html", campuses=campuses)
    
    if request.method == "POST":
        try:
            # ใช้ Model method แทน
            campus.delete_department(dept_key)
            flash("ลบหน่วยงานสำเร็จ", "success")
            
        except ValueError as e:
            flash(str(e), "error")
        except Exception as e:
            flash(f"เกิดข้อผิดพลาด: {str(e)}", "error")
        
        # สำหรับ HTMX: ส่งข้อมูลใหม่กลับไป
        campuses = CampusAndDepartment.objects
        return render_template("campus-and-department/partials/campus-list.html", campuses=campuses)
    
    # GET request - ไม่ต้องแสดง confirmation modal แล้ว เพราะใช้ในหน้าแก้ไข
    flash("ไม่รองรับการเข้าถึงหน้านี้โดยตรง", "error")
    return redirect(url_for("campus_department.index"))
