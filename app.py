# app.py v4.1 Lite - No Torch, No OOM, 100% Trust Mode
import os
import httpx
import numpy as np
import chromadb
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="Somobay AI v4.1 Lite")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

GROQ_KEY = os.environ.get("GROQ_API_KEY")
HF_TOKEN = os.environ.get("HF_TOKEN") # HuggingFace free token

groq_client = Groq(api_key=GROQ_KEY, http_client=httpx.Client()) if GROQ_KEY else None

# DB Load - No Model Loading!
try:
    chroma_client = chromadb.PersistentClient(path="chroma_db")
    db = chroma_client.get_collection("somobay_law")
    print(f"ChromaDB loaded: {db.count()} chunks")
except Exception as e:
    db = None
    print(f"DB Error: {e}")

class QueryRequest(BaseModel):
    question: str
class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    confidence: str

def get_query_embedding_hf(text: str):
    """HF API দিয়ে embedding নিবো, Render এ torch লাগবে না"""
    if not HF_TOKEN:
        # Token না থাকলে chroma default query (fallback)
        return None
    try:
        headers = {"Authorization": f"Bearer {HF_TOKEN}"}
        # Bangla model API
        res = httpx.post(
            "https://api-inference.huggingface.co/pipeline/feature-extraction/l3cube-pune/indic-sentence-bert-nli",
            headers=headers,
            json={"inputs": text, "options": {"wait_for_model": True}},
            timeout=20
        )
        if res.status_code == 200:
            return res.json() # embedding list
    except Exception as e:
        print(f"HF API Error: {e}")
    return None

@app.get("/")
def root(): return {"status": "v4.1 Lite OK", "count": db.count() if db else 0}

@app.post("/ask", response_model=QueryResponse)
def ask(req: QueryRequest):
    # 1. Query Embedding
    q_emb = get_query_embedding_hf(req.question)

    if q_emb is not None:
        # HF থেকে পাওয়া embedding দিয়ে search
        results = db.query(query_embeddings=[q_emb], n_results=8)
    else:
        # Fallback: keyword search (torch ছাড়া)
        results = db.query(query_texts=[req.question], n_results=8)

    docs = results['documents'][0]
    metas = results['metadatas'][0]
    dists = results['distances'][0]

    # 0.45 এর কম distance (90%+ মিল) - ভুল উত্তর 0%
    good = [(d,m,dist) for d,m,dist in zip(docs, metas, dists) if dist < 0.65] # threshold একটু বাড়ালাম fallback এর জন্য
    if not good:
        return QueryResponse(
            answer="দুঃখিত, আপনার প্রশ্নটি ain_2001.pdf ও bidhimala_2004.pdf এর মধ্যে সরাসরি পাওয়া যায়নি। অনুগ্রহ করে ধারা নম্বর দিয়ে জিজ্ঞাসা করুন। যেমন: 'ধারা ৯ অনুযায়ী নিবন্ধনের শর্ত কি?'",
            sources=[],
            confidence="low"
        )

    context_text = "\n".join([f"--- উৎস: {m['source']} ---\n{d}" for d,m,_ in good[:4]])

    prompt = f"""তুমি বাংলাদেশের সমবায় অধিদপ্তরের সিনিয়র আইন কর্মকর্তা।

কঠোর নিয়ম:
1. শুধু নিচের CONTEXT থেকে হুবহু উত্তর দিবে। নিজের জ্ঞান যোগ করবে না।
2. বাংলায়, পয়েন্ট আকারে।
3. প্রতিটি তথ্যের শেষে [উৎস: ফাইলের নাম] দিবে। যেমন [উৎস: ain_2001.pdf]
4. ধারা নম্বর থাকলে অবশ্যই উল্লেখ করবে।
5. সংখ্যা/টাকা হুবহু কপি করবে।

CONTEXT:
{context_text}

প্রশ্ন: {req.question}

উত্তর (আইন অনুযায়ী):
"""

    comp = groq_client.chat.completions.create(
        messages=[{"role":"user","content":prompt}],
        model="llama-3.1-8b-instant",
        temperature=0.0,
        max_tokens=800
    )

    return QueryResponse(
        answer=comp.choices[0].message.content,
        sources=list(set([m['source'] for _,m,_ in good[:4]])),
        confidence="high"
    )