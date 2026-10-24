from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING
from flask import current_app

_client = None
_db = None

def init_store(app):
    global _client, _db
    uri = app.config.get("MONGO_URI")
    if not uri:
        raise RuntimeError("MONGO_URI is missing. Set it in your .env or hosting environment.")
    _client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    _db = _client[app.config.get("MONGO_DB_NAME", "foodiehub")]
    _db.users.create_index([("email", ASCENDING)], unique=True)
    _db.menu_items.create_index([("id", ASCENDING)], unique=True)
    _db.cart_items.create_index([("user_id", ASCENDING), ("menu_item_id", ASCENDING)], unique=True)
    _db.orders.create_index([("id", ASCENDING)], unique=True)
    _client.admin.command("ping")

def col(name):
    if _db is None:
        raise RuntimeError("MongoDB is not initialized")
    return _db[name]

def next_id(name):
    result = col("counters").find_one_and_update(
        {"_id": name}, {"$inc": {"seq": 1}}, upsert=True, return_document=True
    )
    return result["seq"]

def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def clean_doc(doc):
    if not doc: return None
    doc = dict(doc)
    doc.pop("_id", None)
    return doc
