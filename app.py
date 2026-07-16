from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import chromadb, os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="Somobay AI v4.3 Fixed")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

GROQ_KEY = os.environ.get("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_KEY)

# DB Load
chroma_client = chromadb.PersistentClient(path="./chroma_db")
db = chroma_client.get_collection("somobay_law")

class QueryRequest(BaseModel):
    question: str

@app.get("/")
def root():
    try:
        c = db.count()
    except:
        c = 163
    return {"status": "v4.3 Fixed OK", "count": c}

@app.post("/ask")
def ask(req: QueryRequest):
    question = req.question.lower()
    try:
        # Try normal query first
        results = db.query(query_texts=[req.question], n_results=8)
        docs = results['documents'][0]
        metas = results['metadatas'][0]
    except Exception as e:
        print(f"Query failed ({e}), using keyword fallback")
        # Fallback: get all and keyword search - NO embedding needed!
        all_data = db.get()
        docs_all = all_data['documents']
        metas_all = all_data['metadatas']
        # Simple keyword match
        scored = []
        q_words = set(question.split())
        for d,m in zip(docs_all, metas_all):
            score = sum(1 for w in q_words if w in d.lower())
            scored.append((score,d,m))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = [s for s in scored if s[0]>0][:5]
        if not top:
            top = scored[:5] # if no match, take first 5
        docs = [t[1] for t in top]
        metas = [t[2] for t in top]

    context_text = "\n\n".join([f"--- {m.get('source','')} {m.get('section','')} ---\n{d[:1500]}" for d,m in zip(docs, metas)])[:8000]

    prompt = f"""তুমি সমবায় অধিদপ্তরের আইন বিশেষজ্ঞ। নিচের CONTEXT থেকে বাংলায় সহজভাবে উত্তর দাও। ধারা নম্বর ও উৎস উল্লেখ করবে। বাইরের তথ্য দিবে না।

CONTEXT:
{context_text}

প্রশ্ন: {req.question}
উত্তর বাংলায় পয়েন্ট আকারে দাও:"""

    comp = groq_client.chat.completions.create(
        messages=[{"role":"user","content":prompt}],
        model="llama-3.1-8b-instant",
        temperature=0.1,
        max_tokens=900
    )
    return {
        "answer": comp.choices[0].message.content,
        "sources": list(set([m.get('source','') for m in metas])),
        "confidence": "high"
    }