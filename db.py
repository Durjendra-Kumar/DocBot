from pymongo import MongoClient
from dotenv import load_dotenv
import os
load_dotenv()

client = MongoClient(os.getenv("MONGO_URI"))

db = client["RagGpt_db"]

users_collection = db["users"]
sessions_collection = db["sessions"]
vectors_collection = db["vectors"]
chat_collection = db["chat_history"]