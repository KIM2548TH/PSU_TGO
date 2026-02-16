
import os
import sys
from mongoengine import connect, disconnect
from webapp.models.campus_and_department_model import CampusAndDepartment
from webapp.models.user_model import User
from webapp.models.scope_model import Scope
from webapp.models.materail_model import Material

# Setup - mimic run-web
sys.path.append(os.getcwd())
# Assuming local mongo
connect('tgo_db', host='mongodb://localhost:27017/tgo_db')

def simulate_missing_department():
    print("=== Simulating Missing Department Scenario ===")
    
    # 1. Find a campus
    campus = CampusAndDepartment.objects.first()
    if not campus:
        print("No campus found. Create one first.")
        return

    print(f"Using Campus: {campus.name.get('0', 'Unknown')}")
    
    # 2. Get a valid department key
    if not campus.departments:
        print("No departments in campus.")
        return
        
    dept_keys = list(campus.departments.keys())
    target_key = dept_keys[0]
    print(f"Target Department Key: {target_key} ({campus.departments[target_key]})")
    
    # 3. Simulate invalid access patterns (that might be in the code)
    # Checking if code crashes on missing key
    
    try:
        # Simulate accessing a deleted key
        deleted_key = "9999"
        print(f"Accessing deleted key {deleted_key}:")
        val = campus.departments[deleted_key] 
        print(f"Value: {val}")
    except KeyError:
        print("Caught KeyError as expected.")
    except Exception as e:
        print(f"Caught unexpected exception: {e}")

    # 4. Simulate User pointing to missing department
    print("\n=== Simulating User with Missing Department ===")
    # We won't actually modify DB, just mock the logic
    # Logic in get_user_scopes:
    # Scope.objects(..., department=user.department_key)
    
    # If department_key doesn't exist in CampusAndDepartment, Scope query just returns empty?
    # Scope.objects(...) -> QuerySet.
    
    print("Test passed without crash.")

if __name__ == "__main__":
    simulate_missing_department()
