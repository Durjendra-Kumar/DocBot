# 📄 DocBot — RAG-Powered Document Chatbot

A full-stack AI chatbot that lets you upload PDF documents and chat with them in **any language** (Hindi, English, Hinglish, and more). Built with FastAPI, MongoDB, Groq LLaMA 3.1, and Sentence Transformers.

---

## ✨ Features

- 🔐 **User Authentication** — Register & login with secure Argon2 password hashing
- 📁 **PDF Upload** — Upload documents per chat session
- 🤖 **RAG Pipeline** — Retrieval-Augmented Generation using vector similarity search
- 🌐 **Multilingual Support** — Ask questions in Hindi, English, or Hinglish; get replies in the same language
- 💬 **Streaming Responses** — LLM responses stream in real-time
- 🗂️ **Session Management** — Multiple chat sessions per user; auto-named from first message
- 🌙 **Dark / Light Mode** — Theme toggle with local storage persistence
- 🗑️ **Delete Chats** — Remove any session and its history
- 📜 **Chat History** — Full conversation history per session

---

## 🗂️ Project Structure

```
.
├── main.py           # FastAPI app — all routes & endpoints
├── auth.py           # User registration & login logic
├── db.py             # MongoDB connection & collections
├── models.py         # Pydantic request/response models
├── rag_service.py    # Embedding model + vector similarity search
├── session.py        # Session CRUD operations
├── utils.py          # PDF text extraction & chunking
├── templates/
│   └── index.html    # Frontend (single-page app)
├── .env              # Environment variables (not committed)
└── requirements.txt
```

---

## ⚙️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Uvicorn |
| Database | MongoDB (via PyMongo) |
| LLM | LLaMA 3.1 8B (via Groq API) |
| Embeddings | `paraphrase-multilingual-MiniLM-L12-v2` |
| Auth | Argon2 password hashing (passlib) |
| Frontend | HTML + Bootstrap 5 + Vanilla JS |

---

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/docbot.git
cd docbot
```

### 2. Create a Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

> ⚠️ First run will automatically download the multilingual embedding model (~120 MB).

### 4. Set Up Environment Variables

Create a `.env` file in the project root:

```env
MONGO_URI=mongodb://localhost:27017
GROQ_API_KEY=your_groq_api_key_here
```

- Get your **Groq API key** free at [console.groq.com](https://console.groq.com)
- For **MongoDB**, use a local instance or [MongoDB Atlas](https://www.mongodb.com/atlas) (free tier available)

### 5. Run the Server

```bash
uvicorn main:app --reload
```

Open your browser at: **http://localhost:8000**

---

## 📡 API Endpoints

### Auth
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/register` | Register new user |
| `POST` | `/login` | Login & set session cookie |
| `POST` | `/logout` | Clear cookies |

### Sessions
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/create-session` | Create a new chat session |
| `GET` | `/sessions` | Get all sessions for current user |
| `POST` | `/set-session` | Switch to a different session |
| `PATCH` | `/update-session-title` | Auto-update title from first message |
| `DELETE` | `/delete-session` | Delete session & its messages |

### Documents & Chat
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/upload` | Upload a PDF to current session |
| `POST` | `/chat` | Send a message (streaming response) |
| `GET` | `/chat-history` | Fetch all messages in current session |
| `POST` | `/smart-chat` | Chat using all docs across all sessions |

---

## 🌐 Multilingual Support

DocBot uses **`paraphrase-multilingual-MiniLM-L12-v2`** as its embedding model, which supports 50+ languages. This means:

- You can upload an **English PDF** and ask questions in **Hindi**
- The system will find the correct context and the LLM will reply in your language
- Supported: Hindi 🇮🇳, English 🇬🇧, Hinglish, Urdu, French, German, Spanish, and 40+ more

---

## 🔒 Security Notes

- Passwords are hashed with **Argon2** (industry standard)
- Sessions are stored in HTTP-only cookies
- Each session/upload is validated to belong to the authenticated user
- CORS is currently open (`*`) — restrict in production

---

## 📦 MongoDB Collections

| Collection | Purpose |
|---|---|
| `users` | Stores username + hashed password |
| `sessions` | Stores session metadata per user |
| `vectors` | Stores text chunks + embeddings |
| `chat_history` | Stores all chat messages |

---

## 🛠️ Common Issues

**Embedding model downloading slowly?**
The `paraphrase-multilingual-MiniLM-L12-v2` model is ~120 MB and downloads once on first run. It's then cached locally.

**Old uploads not working after model change?**
If you previously used `all-MiniLM-L6-v2`, re-upload your PDFs. Old embeddings are incompatible with the new model.

**MongoDB connection error?**
Make sure MongoDB is running locally (`mongod`) or your Atlas URI is correct in `.env`.

---

## 📄 License

MIT License — free to use and modify.