from pymongo import MongoClient
from urllib.parse import quote_plus

# MongoDB credentials
username = "admin"
password = quote_plus("R211@2o25")  # URL-encode special characters
host = "127.0.0.1"
port = 27017
db_name = "appdb"            # Replace with your database name

# Connect to MongoDB
uri = f"mongodb://{username}:{password}@{host}:{port}/{db_name}?authSource=admin"
client = MongoClient(uri)
db = client[db_name]
collection = db['scope']  # Replace with your collection name

# Find all documents where department = "1"
docs = collection.find({"department": "2"})

new_docs = []
for doc in docs:
    doc.pop("_id")          # Remove original _id
    doc["department"] = "18" # Change department to 3
    new_docs.append(doc)

# Insert duplicated documents
if new_docs:
    collection.insert_many(new_docs)
    print(f"{len(new_docs)} documents duplicated with department changed to 3.")
else:
    print("No documents found with department = '1'.")

