from pymongo import MongoClient
from urllib.parse import quote_plus

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
users_collection = db['users']
scope_collection = db['scope']

def get_all_sub_scopes_by_ghg_scope():
    """
    ดึงซับสโคปทั้งหมดจาก base template แยกตาม ghg_scope
    """
    try:
        # ดึงข้อมูล scope จาก base template
        base_scopes = scope_collection.find({
            "campus": "base",
            "department": "base"
        })
        
        scopes_by_ghg = {1: [], 2: [], 3: []}
        
        for scope in base_scopes:
            ghg_scope = scope.get('ghg_scope')
            ghg_sup_scope = scope.get('ghg_sup_scope')
            
            if ghg_scope in scopes_by_ghg and ghg_sup_scope not in scopes_by_ghg[ghg_scope]:
                scopes_by_ghg[ghg_scope].append(ghg_sup_scope)
        
        # เรียงลำดับ
        for scope_type in scopes_by_ghg:
            scopes_by_ghg[scope_type].sort()
        
        return scopes_by_ghg
    
    except Exception as e:
        print(f"Error getting sub scopes: {e}")
        return {1: [], 2: [], 3: []}

def update_all_users_scopes():
    """
    อัปเดตซับสโคปให้ผู้ใช้ทั้งหมดให้ครบทุกซับสโคป
    """
    try:
        # ดึงซับสโคปทั้งหมดจาก base template
        all_scopes = get_all_sub_scopes_by_ghg_scope()
        
        print("Available sub scopes from base template:")
        for scope_type, sub_scopes in all_scopes.items():
            print(f"  Scope {scope_type}: {sub_scopes}")
        
        if not any(all_scopes.values()):
            print("No sub scopes found in base template. Please create base scopes first.")
            return
        
        # ดึงผู้ใช้ทั้งหมด
        users = users_collection.find({})
        updated_count = 0
        
        for user in users:
            user_id = user['_id']
            username = user.get('username', 'Unknown')
            
            # เตรียมข้อมูลการอัปเดต
            update_data = {
                'ghg_scope_1': all_scopes[1],
                'ghg_scope_2': all_scopes[2], 
                'ghg_scope_3': all_scopes[3],
                'updated_date': None  # ให้เป็น None เหมือนในไฟล์ user_clone.py
            }
            
            # อัปเดตผู้ใช้
            result = users_collection.update_one(
                {'_id': user_id},
                {'$set': update_data}
            )
            
            if result.modified_count > 0:
                updated_count += 1
                print(f"✓ Updated user: {username}")
                print(f"  - Scope 1: {all_scopes[1]}")
                print(f"  - Scope 2: {all_scopes[2]}")
                print(f"  - Scope 3: {all_scopes[3]}")
            else:
                print(f"- No changes for user: {username}")
        
        print(f"\n🎉 Successfully updated {updated_count} users with all sub scopes!")
        
    except Exception as e:
        print(f"❌ Error updating users: {e}")

def main():
    """
    Main function to run the scope update script
    """
    print("🚀 Starting user sub scopes update script...")
    print("=" * 60)
    
    try:
        # ทดสอบการเชื่อมต่อ
        client.admin.command('ping')
        print("✓ Connected to MongoDB successfully")
        
        # รันการอัปเดต
        update_all_users_scopes()
        
    except Exception as e:
        print(f"❌ Connection error: {e}")
    
    finally:
        client.close()
        print("\n🔒 Database connection closed.")

if __name__ == "__main__":
    main()