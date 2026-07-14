import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
import httpx
from dotenv import load_dotenv
import chromadb

load_dotenv()

app = FastAPI(title="Somobay AI", version="2.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Groq সেটআপ ---
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
    print(f"Groq client init failed: {e}")
    client = None

# --- ChromaDB নেটিভ ক্লায়েন্ট ---
try:
    chroma_client = chromadb.PersistentClient(path="chroma_db")
    # আপনার chroma_db তে collection এর নাম কি? সাধারণত "langchain" থাকে
    # যদি না জানেন, প্রথমে সব collection এর নাম প্রিন্ট করে দেখেন
    collections = chroma_client.list_collections()
    print(f"Available collections: {[c.name for c in collections]}")
    
    # ধরে নিলাম নাম "langchain", না হলে এখানে চেঞ্জ করবেন
    collection_name = collections[0].name if collections else "langchain"
    db = chroma_client.get_collection(name=collection_name)
    print(f"ChromaDB loaded successfully. Collection: {collection_name}")
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
        "status": "Somobay AI is Live!",
        "groq_status": "OK" if client else "GROQ_API_KEY missing",
        "db_status": "OK" if db else "ChromaDB missing",
        "db_count": db.count() if db else 0
    }

@app.post("/ask", response_model=QueryResponse)
def ask_question(request: QueryRequest):
    if not client:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY সেট করা নাই")
    if not db:
        raise HTTPException(status_code=500, detail="ChromaDB লোড হয় নাই")
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="প্রশ্ন খালি রাখা যাবে না।")
    
    try:
        # ChromaDB নেটিভ query - embedding অটো ইউজ হবে DB থেকে
        results = db.query(
            query_texts=[request.question],
            n_results=4
        )
        
        docs = results['documents'][0] if results['documents'] else []
        metadatas = results['metadatas'][0] if results['metadatas'] else []
        
        context_text = "\n\n---\n\n".join(docs)
        sources = [m.get('source', 'Unknown') for m in metadatas]

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system", 
                    "content": f"""তুমি একজন বাংলাদেশী সমবায় আইন বিশেষজ্ঞ। তোমার নাম Somobay AI। 
                    নিচের 'প্রসঙ্গ' ব্যবহার করে ইউজারের প্রশ্নের উত্তর দাও। 
                    উত্তর সংক্ষিপ্ত, সহজ বাংলায় দিবে। প্রসঙ্গে না থাকলে বলবে 'দুঃখিত, আমার ডাটাবেসে এই তথ্যটি এখন নেই।'

                    প্রসঙ্গ:
                    {context_text}
                    """
                },
                {"role": "user", "content": request.question}
            ],
            model="llama-3.1-8b-instant",
            temperature=0.1,
            max_tokens=1024,
        )
        answer = chat_completion.choices[0].message.content
        return QueryResponse(answer=answer, sources=list(set(sources)))

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=f"AI সার্ভারে সমস্যা: {str(e)}")