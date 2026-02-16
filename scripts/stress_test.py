import time
import os
import psutil
import sys
from webapp.web import create_app
from webapp.models import User, Scope, Material
from flask_login import login_user
import threading
import random

# Add project root to path
sys.path.append(os.getcwd())

def log_memory(pid, tag=""):
    process = psutil.Process(pid)
    mem = process.memory_info().rss / 1024 / 1024  # MB
    print(f"[{tag}] Memory usage: {mem:.2f} MB")
    return mem

def run_stress_test():
    app = create_app()
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing

    pid = os.getpid()
    log_memory(pid, "Start")

    with app.app_context():
        # Find a user to login
        user = User.objects(roles="admin").first() or User.objects().first()
        if not user:
            print("No user found! Cannot run stress test.")
            return

        print(f"Using user: {user.username}")

        # Find a valid scope
        scope = Scope.objects().first()
        if not scope:
            print("No scope found! Cannot run stress test.")
            return
        
        print(f"Using scope: {scope.ghg_scope}.{scope.ghg_sup_scope}")

        client = app.test_client()

        # Login
        # We simulate login by setting session directly if possible, or via login route
        # Using login_user within a request context is tricky with test_client, 
        # so we use client to login via route.
        # Assuming password is '123456' or we can set a known password.
        # Since we don't know the password, let's try to simulate session transaction.
        
        with client.session_transaction() as sess:
            sess["user_id"] = str(user.id)
            sess["username"] = user.username
            sess["role"] = user.roles[0]
            sess["_user_id"] = str(user.id) # Flask-Login needs this

        log_memory(pid, "After Login")

        for i in range(100):
            # 1. View Emissions Table
            resp = client.get(
                f"/emissions/load-emissions-table?scope_id={scope.ghg_scope}&sub_scope_id={scope.ghg_sup_scope}&year=2024",
                follow_redirects=True
            )
            if resp.status_code != 200:
                print(f"Error loading table: {resp.status_code}")
            
            # 2. Simulate saving materials (which triggers calculation)
            # We need valid head/field from scope
            if scope.head_table:
                head = scope.head_table[0]
                # Need to find a field for this head. 
                from webapp.models import FormAndFormula
                form = FormAndFormula.objects(material_name=head).first()
                if form and form.input_types:
                    field = form.input_types[0].field
                    
                    data = {
                        "scope_id": scope.ghg_scope,
                        "sub_scope_id": scope.ghg_sup_scope,
                        "month_id": 1,
                        "year": 2024,
                        "head": head,
                        "amount": random.uniform(10, 100), # Random amount
                        "input_field": field,
                        f"amount_{1}_{head}_{field}": random.uniform(10, 100) # For multiple save format
                    }
                    
                    resp = client.post(
                        "/emissions/save-materials",
                        data=data,
                        follow_redirects=True
                    )
                    if resp.status_code != 200:
                         # Try with simpler data for single save if that failed
                         pass

            if i % 10 == 0:
                log_memory(pid, f"Iteration {i}")

    log_memory(pid, "End")

if __name__ == "__main__":
    run_stress_test()
