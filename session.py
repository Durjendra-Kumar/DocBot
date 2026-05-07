import uuid
from bson import ObjectId
from db import sessions_collection, users_collection

def create_session(user_id):
    session_id = str(uuid.uuid4())

    sessions_collection.insert_one({
        "session_id": session_id,
        "user_id": user_id,
        "title": "New Chat"
    })

    return session_id

def get_user_sessions(user_id):
    sessions = list(sessions_collection.find({"user_id": user_id}))

    user = users_collection.find_one({"_id": ObjectId(user_id)})
    username = user["username"] if user else None

    for session in sessions:
        session["_id"] = str(session["_id"])
        session["user_id"] = str(session["user_id"])
        session["username"] = username

    return sessions

def get_session(session_id):
    return sessions_collection.find_one({"session_id": session_id})

def update_session_title(session_id, title):
    sessions_collection.update_one(
        {"session_id": session_id},
        {"$set": {"title": title}}
    )