import mongoengine as me
from flask_login import UserMixin, current_user
import datetime

def generate_default_email():
    """
    Generate a unique default email with an incrementing number.
    Ensures no duplicate email is created.
    """
    base = "user"
    domain = "example.com"
    counter = 1

    while True:
        email = f"{base}{counter}@{domain}"
        if not User.objects(email=email).first():
            return email
        counter += 1

def get_all_sub_scopes():
    """
    Get all sub scopes from Scope model where campus='base' and department='base'
    Returns list of all ghg_sup_scope values
    """
    try:
        from .scope_model import Scope
        # Query scopes from base template (campus="base", department="base")
        base_scopes = Scope.objects(campus="base", department="base")
        
        # Get unique ghg_sup_scope values
        sub_scopes = list(set([scope.ghg_sup_scope for scope in base_scopes]))
        sub_scopes.sort()  # Sort for consistency
        print(f"Found {len(sub_scopes)} sub scopes: {sub_scopes}")  # Debug log
        return sub_scopes
    except Exception as e:
        print(f"Error getting sub scopes: {e}")
        return []

def get_sub_scopes_by_scope(scope_number):
    """
    Get sub scopes for specific ghg_scope (1, 2, or 3) from base template
    """
    try:
        from .scope_model import Scope
        # Query scopes from base template with specific ghg_scope
        base_scopes = Scope.objects(campus="base", department="base", ghg_scope=scope_number)
        
        # Get unique ghg_sup_scope values for this scope
        sub_scopes = list(set([scope.ghg_sup_scope for scope in base_scopes]))
        sub_scopes.sort()
        print(f"Found {len(sub_scopes)} sub scopes for scope {scope_number}: {sub_scopes}")  # Debug log
        return sub_scopes
    except Exception as e:
        print(f"Error getting sub scopes for scope {scope_number}: {e}")
        return []

class User(me.Document, UserMixin):
    username = me.StringField(required=True, unique=True)
    name = me.StringField(required=True, default="")  # ชื่อที่แสดงผล
    password = me.StringField(required=True)
    roles = me.ListField(me.StringField(), default=["user"]) 
    email = me.EmailField(required=False, unique=True, sparse=False, default=generate_default_email)
    campus_id = me.StringField(required=True, default="Not yet allocated")
    department_key = me.StringField(
        required=False, unique=False, null=True, default=""
    )
    
    # ฟิลด์สำหรับเก็บซับสโคป 3 ฟิลด์ - ใช้ default=[] แล้วเซ็ตค่าใน UserService
    ghg_scope_1 = me.ListField(me.IntField(), default=list)  # เก็บเลขซับสโคปของ scope 1
    ghg_scope_2 = me.ListField(me.IntField(), default=list)  # เก็บเลขซับสโคปของ scope 2  
    ghg_scope_3 = me.ListField(me.IntField(), default=list)  # เก็บเลขซับสโคปของ scope 3
    
    status = me.StringField(
        required=True, default="active", choices=["active", "disactive"]
    )

    created_date = me.DateTimeField(required=True, default=datetime.datetime.now)
    updated_date = me.DateTimeField(
        required=True, default=datetime.datetime.now, auto_now=True
    )
    last_login_date = me.DateTimeField(
        required=True, default=datetime.datetime.now, auto_now=True
    )

    meta = {"collection": "users", "indexs": ["username"]}

    def set_password(self, password):
        from werkzeug.security import generate_password_hash

        self.password = generate_password_hash(password)

    def check_password(self, password):
        from werkzeug.security import check_password_hash

        return bool(check_password_hash(self.password, password))
        
    def get_display_name(self):
        """Return name if available, otherwise username"""
        return self.name if self.name else self.username
