from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, UploadFile, File, Request, Response, HTTPException, Header
from fastapi.responses import StreamingResponse
from bson import ObjectId
from bson.errors import InvalidId
from groq import Groq
import shutil, os
from dotenv import load_dotenv

from auth import register_user, login_user
from session import create_session, get_user_sessions, get_session, update_session_title
from rag_service import store_chunks, query_rag
from utils import extract_text, chunk_text
from db import chat_collection, users_collection, sessions_collection
from models import *
from fastapi.templating import Jinja2Templates


load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- AUTH ---------------- #

templates = Jinja2Templates(directory="templates")

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"request": request}
    )

@app.post("/register")
def register(data: UserRegister):
    result = register_user(data.username, data.password)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return {"message": "User registered", "user": result}


@app.post("/login")
def login(data: UserLogin, response: Response):
    user = login_user(data.username, data.password)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    response.set_cookie("user_id", user["id"], httponly=True)
    return {"msg": "Login success"}


# ---------------- SESSION ---------------- #

def get_current_user(request: Request):
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


@app.post("/create-session")
def new_session(request: Request, response: Response):
    user_id = get_current_user(request)

    session_id = create_session(user_id)

    # ✅ IMPORTANT FIX
    response.set_cookie("session_id", session_id, httponly=True)

    return {"session_id": session_id}


@app.get("/sessions")
def sessions(request: Request):
    user_id = get_current_user(request)
    return get_user_sessions(user_id)


# ---------------- UPLOAD ---------------- #

@app.post("/upload")
def upload(request: Request, file: UploadFile = File(...)):
    user_id = get_current_user(request)

    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Session not selected")

    # ✅ Validate session belongs to user
    session = get_session(session_id)
    if not session or str(session["user_id"]) != user_id:
        raise HTTPException(status_code=403, detail="Invalid session")

    path = f"temp_{file.filename}"

    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    text = extract_text(path)
    chunks = chunk_text(text)

    store_chunks(session_id, chunks, file.filename, user_id)

    os.remove(path)

    return {"msg": "Uploaded successfully"}


# ---------------- CHAT ---------------- #

def stream_response(query, context):
    # Detect question language for dynamic prompt
    hindi_chars = sum(1 for c in query if '\u0900' <= c <= '\u097F')
    total_chars = len(query.replace(" ", "")) or 1
    hindi_ratio = hindi_chars / total_chars

    has_english = any(c.isascii() and c.isalpha() for c in query)

    if hindi_ratio > 0.5:
        is_hindi = True
        is_hinglish = False
    elif hindi_chars > 0 and has_english:
        is_hindi = False
        is_hinglish = True
    else:
        is_hindi = False
        is_hinglish = False

    if is_hindi:
        lang_instruction = "User ne Hindi mein sawaal kiya hai. Apna jawab HINDI mein do. Thodi bahut English use kar sakte ho."
    elif is_hinglish:
        lang_instruction = "User ne Hinglish mein sawaal kiya hai (Hindi + English mix). Apna jawab bhi Hinglish mein do — Hindi aur English dono mix karke likho, jaise normal Hinglish boli jaati hai."
    else:
        lang_instruction = "The user asked in English. Reply ONLY in English."

    system_prompt = f"""You are a helpful document-based AI assistant.
Answer ONLY using the provided context. Do not use outside knowledge.
If the answer is not found in the context, say exactly this in the user's language: "This information is not available in the uploaded document."

LANGUAGE RULE (strictly follow this):
{lang_instruction}

Keep your answer clear, accurate, and concise.
"""

    user_prompt = f"Context:\n{context}\n\nQuestion:\n{query}"

    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        stream=True,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )

    for chunk in completion:
        yield chunk.choices[0].delta.content or ""


def get_full_response(query, context):
    answer = ""
    for chunk in stream_response(query, context):
        answer += chunk
    return answer


@app.post("/chat")
def chat(data: ChatRequest, 
         request: Request, 
         session_id: str = Header(default=None)
):
    user_id = get_current_user(request)

    session_id = session_id or request.cookies.get("session_id")

    if not session_id:
        raise HTTPException(status_code=400, detail="Session not selected")

    session = get_session(session_id)
    
    if not session or str(session["user_id"]) != user_id:
        raise HTTPException(status_code=403, detail="Invalid session")

    context = query_rag(session_id, user_id, data.query)

    if not context or context.strip() == "":
        raise HTTPException(
            status_code=400,
            detail="No documents uploaded. Please upload PDFs before chatting."
    )

    # Save user message
    chat_collection.insert_one({
        "session_id": session_id,
        "role": "user",
        "content": data.query
    })

    def stream():
        answer = ""
        for chunk in stream_response(data.query, context):
            answer += chunk
            yield chunk

        # Save assistant response
        chat_collection.insert_one({
            "session_id": session_id,
            "role": "assistant",
            "content": answer
        })

    return StreamingResponse(stream(), media_type="text/plain")


# ---------------- CHAT HISTORY ---------------- #

@app.get("/chat-history")
def get_chat_history(request: Request):
    user_id = get_current_user(request)

    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Session not selected")

    chats = list(chat_collection.find(
        {"session_id": session_id},
        {"_id": 0}
    ))

    return {"messages": chats}


# ---------------- LOGOUT ---------------- #

@app.post("/logout")
def logout(response: Response):
    response.delete_cookie("user_id")
    response.delete_cookie("session_id")

    return {"message": "Logged out"}

@app.post("/set-session")
def set_session(session_id: str, response: Response, request: Request):
    user_id = get_current_user(request)

    session = get_session(session_id)

    if not session or session["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Invalid session")

    response.set_cookie("session_id", session_id, httponly=True)

    return {"msg": "Session switched"}


@app.post("/smart-chat")
def smart_chat(data: SmartChatRequest):

    # 🔍 1. Validate user
    # user = users_collection.find_one({"_id": ObjectId(data.user_id)})

    

    try:
        user = users_collection.find_one({"_id": ObjectId(data.user_id)})
    except InvalidId:
        user = users_collection.find_one({"_id": data.user_id})

    if not user:
        # 🔥 fallback if user_id stored as string field
        user = users_collection.find_one({"user_id": data.user_id})

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 🔥 2. ALWAYS create new session
    new_session_id = create_session(data.user_id)

    # ---------------- CONTEXT LOGIC ----------------

    if data.context is True:
        final_context = query_rag(
            session_id=None,
            user_id=data.user_id,
            query=data.query,
            use_all_context=True
        )

        if not final_context or final_context.strip() == "":
            raise HTTPException(
                status_code=400,
                detail="No previous context found for this user"
            )

        mode = "all_context"

    else:
        raise HTTPException(
            status_code=400,
            detail="Context is required. Cannot chat without context."
        )

    # ---------------- LLM CALL ----------------

    answer = get_full_response(data.query, final_context)

    # ---------------- SAVE CHAT ----------------

    chat_collection.insert_one({
        "user_id": ObjectId(data.user_id),
        "session_id": new_session_id,
        "query": data.query,
        "response": answer,
        "context_mode": mode
    })

    return {
        "response": answer,
        "session_id": new_session_id,
        "mode": mode
    }


@app.delete("/delete-session")
def delete_session(session_id: str):
    sessions_collection.delete_one({"session_id": session_id})
    chat_collection.delete_many({"session_id": session_id})
    return {"msg": "deleted"}

@app.patch("/update-session-title")
def update_title(session_id: str, title: str, request: Request):
    user_id = get_current_user(request)
    session = get_session(session_id)
    if not session or str(session["user_id"]) != user_id:
        raise HTTPException(status_code=403, detail="Invalid session")
    update_session_title(session_id, title[:60])
    return {"msg": "Title updated"}