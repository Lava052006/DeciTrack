import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")

try:
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)

    # Test the connection
    client.admin.command("ping")

    print("MongoDB connected successfully!")

    db = client[DATABASE_NAME]
    print("Database:", db.name)

    client.close()

except Exception as e:
    print("MongoDB connection failed:", e)