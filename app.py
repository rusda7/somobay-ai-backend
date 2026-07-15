import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
import httpx
from dotenv import load_dotenv
import chromadb

load_dotenv()

app = FastAPI(title="Somobay AI", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Groq ---
GROQ_KEY = os.environ.get("GROQ_API_KEY")
print(f"GROQ_API_KEY Found: {bool(GROQ_KEY)}")

try:
    if GROQ_KEY:
        http_client = httpx.Client()
        client = Groq(api_key=GROQ_KEY, http_client=http_client)
        print("Groq client initialized successfully")
    else:
        client = None
except Exception as e:
    print(f"Groq init failed: {e}")
    client = None

# --- ChromaDB 1.5.9 ---
db = None
try:
    chroma_client = chromadb.PersistentClient(path="chroma_db")
    cols = chroma_client.list_collections()
    print(f"Available collections: {[c.name for c in cols]}")

    if cols:
        db = cols[0]
        print(f"ChromaDB loaded: {db.name}, count: {db.count()}")
    else:
        db = None
except Exception as e:
    print(f"ChromaDB load failed: {e}")
    db = None

class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    answer: str
    sources: list[str] = []

@app.get("/")
def read_root():
    return {
        "status": "Somobay AI Live v3.0 with ChromaDB 1.5.9",
        "groq": "OK" if client else "Missing",
        "db": "OK" if db else "Missing",
        "count": db.count() if db else 0
    }

@app.post("/ask", response_model=QueryResponse)
def ask_question(request: QueryRequest):
    if not client:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY missing")
    if not db:
        raise HTTPException(status_code=500, detail="ChromaDB not loaded")
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="প্রশ্ন খালি")

    try:
        results = db.query(query_texts=[request.question], n_results=4)
        docs = results.get('documents', [[]])[0]
        metadatas = results.get('metadatas', [[]])[0]

        if not docs:
            return QueryResponse(answer="দুঃখিত, ডাটাবেসে এই তথ্যটি নেই।", sources=[])

        context = "\n\n---\n\n".join(docs)
        sources = [m.get('source', 'Unknown') for m in metadatas]

        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": f"""তুমি বাংলাদেশী সমবায় আইন বিশেষজ্ঞ। নাম Somobay AI।
                প্রসঙ্গ দিয়ে উত্তর দাও। সহজ বাংলায়। না থাকলে বলবে 'ডাটাবেসে নেই'।

                প্রসঙ্গ:
                {context}
                """},
                {"role": "user", "content": request.question}
            ],
            model="llama-3.1-8b-instant",
            temperature=0.1,
            max_tokens=1024,
        )
        answer = completion.choices[0].message.content
        return QueryResponse(answer=answer, sources=list(set(sources)))
    except Exception as e:
        print(f"Ask error: {e}")
        raise HTTPException(status_code=500, detail=str(e))