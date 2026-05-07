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
    system_prompt = """
    You are a helpful document-based AI assistant.
    Answer ONLY from the provided context.
    If the answer is not in the context, say: "Please ask a valid question related to the document."

    IMPORTANT: Detect the language of the user's question and ALWAYS reply in that SAME language.
    For example:
    - If the question is in Hindi, reply in Hindi.
    - If the question is in English, reply in English.
    - If the question is in Hinglish (mixed Hindi-English), reply in Hinglish.

    Keep answers clear and concise.
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