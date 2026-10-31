from pymongo import MongoClient
from app.config import settings

client = MongoClient(
    settings.mongodb_uri,
    serverSelectionTimeoutMS=5000
)

database = client[settings.database_name]


def check_database_connection():
    try:
        client.admin.command("ping")
        return True
    except Exception:
        return False