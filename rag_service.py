from sentence_transformers import SentenceTransformer
from db import vectors_collection
import uuid

model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

def store_chunks(session_id, chunks, filename, user_id):
    embeddings = model.encode(chunks).tolist()

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
    import numpy as np
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def query_rag(session_id, user_id, query, use_all_context=False):

    #  Step 1: create query embedding
    query_embedding = model.encode([query])[0]

    #  Step 2: choose data source
    if use_all_context:
        docs = list(vectors_collection.find({"user_id": user_id}))
    else:
        docs = list(vectors_collection.find({"session_id": session_id}))

    #  no data
    if not docs:
        return None

    #  Step 3: score using cosine similarity
    scored = []
    for doc in docs:
        score = cosine_similarity(query_embedding, doc["embedding"])
        scored.append((score, doc["text"]))   # make sure key is correct

    # 🔥 Step 4: sort by relevance
    scored.sort(key=lambda x: x[0], reverse=True)

    # 🔥 Step 5: take top-k chunks
    top_chunks = [x[1] for x in scored[:5]]

    return " ".join(top_chunks)