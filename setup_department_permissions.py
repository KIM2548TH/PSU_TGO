from pymongo import MongoClient
from urllib.parse import quote_plus
import datetime

# MongoDB credentials
username = "admin"
password = quote_plus("R211@2o25")  # URL-encode special characters
host = "127.0.0.1"
port = 27017
db_name = "appdb"

# Connect to MongoDB
uri = f"mongodb://{username}:{password}@{host}:{port}/{db_name}?authSource=admin"
client = MongoClient(uri)
db = client[db_name]

# Collections
permission_collection = db['permission']

def create_department_management_permissions():
    """
    สร้าง permission ทั้ง 3 สิทธิ์ของหน้า department management
    """
    try:
        # กำหนด permission ทั้ง 3 สิทธิ์ตามที่ใช้ในโค้ด department_management.py
        permissions = [
            {
                "name": "เข้าถึงหน้าจัดการผู้ใช้ในหน่วยงาน",
                "description": "สิทธิ์ในการเข้าถึงและดูรายการผู้ใช้ในหน่วยงานเดียวกัน",
                "created_date": datetime.datetime.now()
            },
            {
                "name": "แก้ไขข้อมูลผู้ใช้ในหน่วยงาน", 
                "description": "สิทธิ์ในการแก้ไข scope ย่อยและ status ของผู้ใช้ในหน่วยงานเดียวกัน",
                "created_date": datetime.datetime.now()
            },
            {
                "name": "สร้างผู้ใช้ใหม่ในหน่วยงาน",
                "description": "สิทธิ์ในการสร้างผู้ใช้ใหม่ในหน่วยงานเดียวกัน",
                "created_date": datetime.datetime.now()
            }
        ]
        
        created_count = 0
        updated_count = 0
        
        for perm in permissions:
            # ตรวจสอบว่า permission นี้มีอยู่แล้วหรือไม่
            existing_perm = permission_collection.find_one({"name": perm["name"]})
            
            if existing_perm:
                # อัปเดต description ถ้ามี permission อยู่แล้ว
                result = permission_collection.update_one(
                    {"name": perm["name"]},
                    {"$set": {
                        "description": perm["description"],
                        "created_date": existing_perm.get("created_date", datetime.datetime.now())
                    }}
                )
                if result.modified_count > 0:
                    updated_count += 1
                    print(f"✓ Updated permission: {perm['name']}")
                else:
                    print(f"- Permission already exists (no changes): {perm['name']}")
            else:
                # สร้าง permission ใหม่
                result = permission_collection.insert_one(perm)
                created_count += 1
                print(f"✓ Created new permission: {perm['name']}")
                print(f"  - Description: {perm['description']}")
                print(f"  - ID: {result.inserted_id}")
        
        print(f"\n🎉 Summary:")
        print(f"  - Created: {created_count} new permissions")
        print(f"  - Updated: {updated_count} existing permissions")
        print(f"  - Total department management permissions: {len(permissions)}")
        
    except Exception as e:
        print(f"❌ Error creating permissions: {e}")

def list_all_permissions():
    """
    แสดงรายการ permission ทั้งหมดในระบบ
    """
    try:
        print("\n📋 All permissions in database:")
        print("-" * 80)
        
        permissions = permission_collection.find({}).sort("name", 1)
        count = 0
        
        for perm in permissions:
            count += 1
            name = perm.get('name', 'Unknown')
            description = perm.get('description', 'No description')
            created_date = perm.get('created_date', 'Unknown')
            
            print(f"{count}. {name}")
            print(f"   Description: {description}")
            print(f"   Created: {created_date}")
            print()
        
        if count == 0:
            print("No permissions found in database.")
        else:
            print(f"Total: {count} permissions")
            
    except Exception as e:
        print(f"❌ Error listing permissions: {e}")

def main():
    """
    Main function to run the permission creation script
    """
    print("🚀 Starting department management permissions setup...")
    print("=" * 70)
    
    try:
        # ทดสอบการเชื่อมต่อ
        client.admin.command('ping')
        print("✓ Connected to MongoDB successfully")
        
        # สร้าง permission
        create_department_management_permissions()
        
        # แสดงรายการ permission ทั้งหมด
        list_all_permissions()
        
    except Exception as e:
        print(f"❌ Connection error: {e}")
    
    finally:
        client.close()
        print("\n🔒 Database connection closed.")

if __name__ == "__main__":
    main()