import os
import uuid
import numpy as np
from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from db import vectors_collection

load_dotenv()

HF_API_KEY = os.getenv("HF_API_KEY")
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

hf_client = InferenceClient(api_key=HF_API_KEY)


def get_embeddings(texts: list) -> list:
    """
    Use HuggingFace InferenceClient to get embeddings.
    Handles URL routing automatically.
    """
    result = hf_client.feature_extraction(texts, model=EMBEDDING_MODEL)
    embeddings = np.array(result)

    # If 3D (batch, tokens, dim) → mean pool across tokens
    if embeddings.ndim == 3:
        embeddings = embeddings.mean(axis=1)

    return embeddings.tolist()


def store_chunks(session_id, chunks, filename, user_id):
    embeddings = get_embeddings(chunks)

    data = []
    for i in range(len(chunks)):
        data.append({
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "user_id": user_id,
            "text": chunks[i],
            "embedding": embeddings[i],
            "source": filename
        })

    vectors_collection.insert_many(data)


def cosine_similarity(a, b):
    a, b = np.array(a), np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def query_rag(session_id, user_id, query, use_all_context=False):

    # Step 1: Get query embedding
    query_embedding = get_embeddings([query])[0]

    # Step 2: Choose data source
    if use_all_context:
        docs = list(vectors_collection.find({"user_id": user_id}))
    else:
        docs = list(vectors_collection.find({"session_id": session_id}))

    if not docs:
        return None

    # Step 3: Cosine similarity scoring
    scored = []
    for doc in docs:
        score = cosine_similarity(query_embedding, doc["embedding"])
        scored.append((score, doc["text"]))

    # Step 4: Sort and return top-k
    scored.sort(key=lambda x: x[0], reverse=True)
    top_chunks = [x[1] for x in scored[:5]]

    return " ".join(top_chunks)