# app.py v4.0 - Trust & Accuracy Mode
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
import httpx, chromadb
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="Somobay AI v4 - Trust Mode")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

GROQ_KEY = os.environ.get("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_KEY, http_client=httpx.Client()) if GROQ_KEY else None
embed_model = SentenceTransformer('l3cube-pune/indic-sentence-bert-nli')

try:
    chroma_client = chromadb.PersistentClient(path="chroma_db")
    db = chroma_client.get_collection("somobay_law")
    print(f"DB Count: {db.count()}")
except:
    db = None

class QueryRequest(BaseModel):
    question: str
class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    confidence: str

@app.get("/")
def root(): return {"status": "Trust Mode v4", "count": db.count() if db else 0}

@app.post("/ask", response_model=QueryResponse)
def ask(req: QueryRequest):
    q_emb = embed_model.encode(req.question).tolist()
    results = db.query(query_embeddings=[q_emb], n_results=8)
    docs = results['documents'][0]
    metas = results['metadatas'][0]
    dists = results['distances'][0]

    # শুধু 0.35 এর কম দূরত্ব (90%+ মিল) নিবো
    good = [(d,m,dist) for d,m,dist in zip(docs, metas, dists) if dist < 0.45]
    if not good:
        return QueryResponse(
            answer="দুঃখিত, আপনার প্রশ্নটি সমবায় সমিতি আইন ২০০১ ও সমবায় সমিতি বিধিমালা ২০০৪ এর মধ্যে সরাসরি পাওয়া যায়নি। অনুগ্রহ করে প্রশ্নটি অন্যভাবে করুন অথবা নিকটস্থ সমবায় অফিসে যোগাযোগ করুন।\n\nআপনি জিজ্ঞাসা করতে পারেন: 'ধারা ১৫ অনুযায়ী নিবন্ধনের শর্ত কি?'",
            sources=[],
            confidence="low"
        )

    context = "\n\n--- [{}] ---\n{}\n".format
    context_text = "\n".join([f"--- উৎস: {m['source']} ---\n{d}" for d,m,_ in good[:4]])

    prompt = f"""তুমি বাংলাদেশের সমবায় অধিদপ্তরের সিনিয়র আইন কর্মকর্তা। তোমার নাম Somobay AI।

কঠোর নিয়ম:
1. শুধুমাত্র নিচের আইনি CONTEXT থেকে হুবহু তথ্য নিয়ে উত্তর দিবে। নিজের জ্ঞান যোগ করবে না।
2. উত্তর বাংলায়, সহজ ভাষায়, পয়েন্ট আকারে দিবে।
3. প্রতিটি তথ্যের শেষে [উৎস: ফাইলের নাম] উল্লেখ করবে। যেমন: [উৎস: somobay_ain_2001.pdf]
4. যদি সংখ্যা/টাকা/শতাংশ থাকে, CONTEXT থেকে হুবহু কপি করবে, বানাবে না।
5. ধারা নম্বর থাকলে অবশ্যই উল্লেখ করবে।

CONTEXT:
{context_text}

প্রশ্ন: {req.question}

উত্তর (বিশ্বস্ত, আইন অনুযায়ী):
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
        confidence="high" if good[0][2] < 0.3 else "medium"
    )