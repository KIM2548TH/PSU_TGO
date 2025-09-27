from pymongo import MongoClient
from urllib.parse import quote_plus

# MongoDB credentials
username = "admin"
password = quote_plus("R211@2o25")  # URL-encode special characters
host = "127.0.0.1"
port = 27017
db_name = "appdb"   # ✅ your DB name

# Connect to MongoDB
uri = f"mongodb://{username}:{password}@{host}:{port}/{db_name}?authSource=admin"
client = MongoClient(uri)
db = client[db_name]
collection = db['users']  # Replace with your users collection name

# Find the existing admin user
admin_doc = collection.find_one({"username": "user002"})

if admin_doc:
    admin_doc.pop("_id")  # remove original _id

    # Loop to create admins from admin003 to admin020
    for i, dept_key in enumerate(range(4, 22), start=3):
        new_doc = admin_doc.copy()
        new_doc["username"] = f"user{str(i).zfill(3)}"
        new_doc["email"] = f"{new_doc['username']}@example.com"  # ✅ email matches username
        new_doc["department_key"] = str(dept_key)

        # ✅ Set dates to None
        new_doc["created_date"] = None
        new_doc["updated_date"] = None
        new_doc["last_login_date"] = None

        # Insert one by one
        result = collection.insert_one(new_doc)
        print(f"Inserted {new_doc['username']} with _id: {result.inserted_id}")

else:
    print("Admin user not found.")

