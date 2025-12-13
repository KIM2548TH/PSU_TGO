from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from flask_login import login_required, logout_user, current_user
from werkzeug.utils import secure_filename
from PIL import Image
import os
from ..forms.user_form import LoginForm, RegisterForm, EditUserForm, EditprofileForm
from ...services.user_service import UserService
from ...models import User, Role, Permission, CampusAndDepartment

module = Blueprint("profile", __name__, url_prefix="/profile")

# Configuration for file upload
UPLOAD_FOLDER = 'webapp/web/static/uploads/profile_pictures'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_IMAGE_SIZE = (500, 500)  # Maximum dimensions for profile picture
JPEG_QUALITY = 85  # Quality for JPEG compression (1-100)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_upload_folder():
    """Ensure the upload folder exists"""
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

def compress_and_resize_image(input_path, output_path, max_size=MAX_IMAGE_SIZE, quality=JPEG_QUALITY):
    """
    Compress and resize image to reduce file size
    Returns True if successful, False otherwise
    """
    try:
        # Open image
        with Image.open(input_path) as img:
            # Convert RGBA to RGB if needed (for JPEG compatibility)
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Resize image while maintaining aspect ratio
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Save as optimized JPEG
            img.save(output_path, 'JPEG', quality=quality, optimize=True)
            
        return True
    except Exception as e:
        print(f"Error compressing image: {e}")
        return False

def delete_old_profile_picture(user):
    """Delete old profile picture file if exists"""
    try:
        if user.profile_picture:
            # Extract filename from URL
            old_filename = user.profile_picture.split('/')[-1]
            old_filepath = os.path.join(UPLOAD_FOLDER, old_filename)
            
            # Delete file if exists
            if os.path.exists(old_filepath):
                os.remove(old_filepath)
                print(f"Deleted old profile picture: {old_filepath}")
                return True
    except Exception as e:
        print(f"Error deleting old profile picture: {e}")
    return False

# ดู profile ของ user ใด ๆ (readonly ถ้าไม่ใช่เจ้าของ)
@module.route("/view/<username>", methods=["GET"])
@login_required
def view_profile(username):
    user = User.objects(username=username).first()
    if not user:
        return render_template("/profile/profile.html", error_msg="ไม่พบผู้ใช้")
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(user.campus_id, user.department_key)
    is_owner = (current_user.username == user.username)
    return render_template("/profile/profile.html", user=user, is_owner=is_owner)

@module.route("/", methods=["get", "post"])
@login_required
def profile():
    user = current_user
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(user.campus_id,user.department_key)

    print(user.campus)
    return render_template("/profile/profile.html", user=user, is_owner=True)


@module.route("/load-edit-profile", methods=["GET", "POST"])
@login_required
def load_edit_profile():
    user = current_user  # ใช้ current_user เพื่อดึงข้อมูลผู้ใช้ที่ล็อกอินอยู่
    user.campus = CampusAndDepartment.get_campus_name(user.campus_id)
    user.department = CampusAndDepartment.get_department_name(user.campus_id,user.department_key)
    if not user:
        return jsonify({"error": "User not found"}), 404

    form = EditprofileForm()
    if request.method == "POST":
        # กรอกข้อมูลจากฟอร์ม (ไม่รวม campus และ department)
        form.username.data = user.username  # ไม่ให้แก้ไข username
        form.name.data = request.form.get("name")  # เพิ่มฟิลด์ name
        form.email.data = request.form.get("email")
        # เก็บ campus และ department เดิมไว้ (ไม่ให้แก้ไข)
        form.campus.data = user.campus
        form.department.data = user.department

        # เรียกใช้ UserService เพื่อแก้ไขข้อมูล
        edit_result = UserService.edit_profile(form)
        if not edit_result["success"]:
            return render_template(
                "/profile/form-edit-profile.html",
                user=user,
                form=form,
                error_msg=edit_result["error_msg"],
            )
        return redirect(url_for("profile.profile"))

    # แสดงฟอร์มพร้อมข้อมูลผู้ใช้งาน
    form.username.data = user.username
    form.name.data = user.name  # เพิ่มฟิลด์ name
    form.email.data = user.email
    form.campus.data = user.campus
    form.department.data = user.department

    return render_template(
        "/profile/form-edit-profile.html",
        user=user,
        form=form,
    )


@module.route("/load-check-password-form", methods=["GET"])
@login_required
def load_check_password_form():
    return render_template("/profile/form-check-password.html")

@module.route("/check-current-password", methods=["POST"])
@login_required
def check_current_password():
    current_password = request.form.get("current_password")
    if not current_user.check_password(current_password):
        return render_template("/profile/form-check-password.html", error_msg="รหัสผ่านไม่ถูกต้อง")
    return render_template("/profile/form-new-password.html")

@module.route("/change-new-password", methods=["POST"])
@login_required
def change_new_password():
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")
    if new_password != confirm_password:
        return render_template("/profile/form-new-password.html", error_msg="รหัสผ่านไม่ตรงกัน")
    
    result = UserService.change_password(new_password)
    if not result["success"]:
        return render_template("/profile/form-new-password.html", error_msg=result["error_msg"])
    
    return render_template("success/success.html")

@module.route("/upload-picture", methods=["POST"])
@login_required
def upload_picture():
    """Handle profile picture upload"""
    try:
        # Check if file is present
        if 'profile_picture' not in request.files:
            return jsonify({"success": False, "message": "ไม่พบไฟล์"}), 400
        
        file = request.files['profile_picture']
        
        # Check if file is selected
        if file.filename == '':
            return jsonify({"success": False, "message": "ไม่ได้เลือกไฟล์"}), 400
        
        # Check if file is allowed
        if file and allowed_file(file.filename):
            ensure_upload_folder()
            
            # Delete old profile picture first
            delete_old_profile_picture(current_user)
            
            # Create unique filename using username (always save as .jpg after compression)
            new_filename = f"{current_user.username}_{current_user.id}.jpg"
            temp_filepath = os.path.join(UPLOAD_FOLDER, f"temp_{new_filename}")
            final_filepath = os.path.join(UPLOAD_FOLDER, new_filename)
            
            # Save the uploaded file temporarily
            file.save(temp_filepath)
            
            # Compress and resize the image
            if compress_and_resize_image(temp_filepath, final_filepath):
                # Remove temporary file
                if os.path.exists(temp_filepath):
                    os.remove(temp_filepath)
                
                # Update user profile picture path in database
                profile_picture_url = f"/static/uploads/profile_pictures/{new_filename}?v={int(os.path.getmtime(final_filepath))}"
                current_user.profile_picture = profile_picture_url
                current_user.save()
                
                # Get file size for logging
                file_size = os.path.getsize(final_filepath)
                print(f"Profile picture saved: {new_filename} ({file_size} bytes)")
                
                return jsonify({
                    "success": True, 
                    "message": "บันทึกรูปโปรไฟล์สำเร็จ",
                    "profile_picture_url": profile_picture_url
                }), 200
            else:
                # Clean up on compression failure
                if os.path.exists(temp_filepath):
                    os.remove(temp_filepath)
                return jsonify({"success": False, "message": "ไม่สามารถประมวลผลรูปภาพได้"}), 500
        else:
            return jsonify({"success": False, "message": "ประเภทไฟล์ไม่ถูกต้อง (อนุญาตเฉพาะ png, jpg, jpeg, gif, webp)"}), 400
            
    except Exception as e:
        print(f"Error uploading profile picture: {e}")
        return jsonify({"success": False, "message": "เกิดข้อผิดพลาดในการบันทึกรูปภาพ"}), 500