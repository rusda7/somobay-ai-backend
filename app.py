import os, httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
import chromadb
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="Somobay AI v4.2 Fast")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

GROQ_KEY = os.environ.get("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

try:
    chroma_client = chromadb.PersistentClient(path="chroma_db")
    db = chroma_client.get_collection("somobay_law")
    print(f"ChromaDB loaded: {db.count()} chunks")
except Exception as e:
    db = None
    print(f"DB Error: {e}")

class QueryRequest(BaseModel):
    question: str

@app.get("/")
def root():
    return {"status": "v4.2 Fast OK", "count": db.count() if db else 0}

@app.post("/ask")
def ask(req: QueryRequest):
    # Fast keyword search - no HF, no torch, super fast
    results = db.query(query_texts=[req.question], n_results=8)
    docs = results['documents'][0]
    metas = results['metadatas'][0]

    if not docs:
        return {"answer": "দুঃখিত, এই বিষয়ে আইনে সরাসরি কিছু পাওয়া যায়নি। ধারা নম্বর দিয়ে জিজ্ঞাসা করুন।", "sources": [], "confidence": "low"}

    context_text = "\n".join([f"--- উৎস: {m['source']} ---\n{d}" for d,m in zip(docs, metas)][:4])
    prompt = f"""তুমি সমবায় আইন বিশেষজ্ঞ। শুধু CONTEXT থেকে বাংলায় পয়েন্ট আকারে উত্তর দাও। ধারা নম্বর উল্লেখ করবে। [উৎস: ফাইলের নাম] দিবে।

CONTEXT:
{context_text}

প্রশ্ন: {req.question}
উত্তর:
"""
    comp = groq_client.chat.completions.create(
        messages=[{"role":"user","content":prompt}],
        model="llama-3.1-8b-instant",
        temperature=0.0,
        max_tokens=800
    )
    return {"answer": comp.choices[0].message.content, "sources": list(set([m['source'] for m in metas[:4]])), "confidence": "high"}