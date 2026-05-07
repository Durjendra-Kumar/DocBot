from passlib.context import CryptContext
from db import users_collection
import uuid

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_password(password):
    return pwd_context.hash(password)

def verify_password(password, hashed):
    return pwd_context.verify(password, hashed)

def register_user(username, password):
    if users_collection.find_one({"username": username}):
        return {"error": "User already exists"}

    user = {
        "username": username,
        "password": hash_password(password)
    }

    result = users_collection.insert_one(user)

    return {
        "id": str(result.inserted_id),
        "username": username,
    }

def login_user(username, password):
    user = users_collection.find_one({"username": username})

    if not user or not verify_password(password, user["password"]):
        return None

    return { 
        "id": str(user["_id"]),
        "username": user["username"]
    }
