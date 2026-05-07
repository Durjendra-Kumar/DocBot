from pydantic import BaseModel
from typing import Optional

class UserRegister(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class ChatRequest(BaseModel):
    query: str
    # user_id: str

class SmartChatRequest(BaseModel):
    user_id: str
    session_id: Optional[str]
    context: bool
    query: str
