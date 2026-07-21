import os
import re
import pathlib
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

app = FastAPI(title="Somobay AI Backend - Full Law DB")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== Load Knowledge Base ==========
BASE_DIR = pathlib.Path(__file__).parent
AIN_PATH = BASE_DIR / "ain_2001.txt"
BIDI_PATH = BASE_DIR / "bidhimala_2004.txt"

# Fallback: if files not in backend folder, try current dir
if not AIN_PATH.exists():
    alt = pathlib.Path("/mnt/data/ain_2001.txt")
    if alt.exists():
        AIN_PATH = alt
if not BIDI_PATH.exists():
    alt = pathlib.Path("/mnt/data/bidhimala_2004.txt")
    if alt.exists():
        BIDI_PATH = alt

def load_text(path):
    if path.exists():
        try:
            return path.read_text(encoding='utf-8', errors='ignore')
        except:
            return path.read_text(encoding='latin-1', errors='ignore')
    return ""

AIN_TEXT = load_text(AIN_PATH)
BIDI_TEXT = load_text(BIDI_PATH)

print(f"Loaded Ain: {len(AIN_TEXT)} chars, Bidi: {len(BIDI_TEXT)} chars")

# Chunking
def chunk_text(text, chunk_size=800, overlap=150):
    chunks = []
    if not text:
        return chunks
    # Split by paragraph first
    paras = re.split(r'\n\s*\n', text)
    for para in paras:
        para = para.strip()
        if len(para) < 30:
            continue
        if len(para) <= chunk_size:
            chunks.append(para)
        else:
            # sliding window for long para
            for i in range(0, len(para), chunk_size - overlap):
                c = para[i:i+chunk_size]
                if len(c) > 100:
                    chunks.append(c)
    return chunks

AIN_CHUNKS = chunk_text(AIN_TEXT)
BIDI_CHUNKS = chunk_text(BIDI_TEXT)
ALL_CHUNKS = [{"text": c, "source": "সমবায় সমিতি আইন, ২০০১"} for c in AIN_CHUNKS] + \
             [{"text": c, "source": "সমবায় সমিতি বিধিমালা, ২০০৪"} for c in BIDI_CHUNKS]

print(f"Total chunks: {len(ALL_CHUNKS)}")

# Simple cache
CACHE = {}

# BM25-like keyword search (no external lib)
def tokenize(s):
    # keep Bengali + English words
    return re.findall(r'[\u0980-\u09FFa-zA-Z0-9]+', s.lower())

def score_chunk(query_tokens, chunk_tokens):
    # count overlap + bonus for exact phrase
    q_set = set(query_tokens)
    c_set = set(chunk_tokens)
    overlap = len(q_set & c_set)
    # extra weight for important legal words
    bonus = 0
    for qt in query_tokens:
        if len(qt) > 2 and qt in chunk_tokens:
            bonus += chunk_tokens.count(qt) * 0.2
    return overlap + bonus

def retrieve(query, top_k=4):
    q_tokens = tokenize(query)
    if not q_tokens:
        return []
    scored = []
    for idx, ch in enumerate(ALL_CHUNKS):
        c_tokens = tokenize(ch["text"])
        s = score_chunk(q_tokens, c_tokens)
        # Boost if query contains numbers like ধারা ১৭ and chunk contains same
        if "ধারা" in query or "dhar" in query.lower():
            m = re.search(r'ধারা\s*([০-৯0-9]+)', query)
            if m and m.group(1) in ch["text"]:
                s += 3
        scored.append((s, idx))
    scored.sort(reverse=True, key=lambda x: x[0])
    top = [ALL_CHUNKS[i] for sc,i in scored[:top_k] if sc>0]
    if not top:
        top = ALL_CHUNKS[:2] if ALL_CHUNKS else []
    return top

# Special answers for common meta questions
META_INFO = {
    "অধ্যায়": "সমবায় সমিতি আইন, ২০০১ এ মূলত ১৩টি অধ্যায় এবং ৯০টি ধারা ছিল। পরবর্তীতে সংশোধনের মাধ্যমে বর্তমানে ৮৮টি ধারা কার্যকর রয়েছে।",
    "ধারা": "সমবায় সমিতি আইন, ২০০১ এ ৯০টি ধারা ছিল, সংশোধনের পর বর্তমানে কার্যকর ধারা ৮৮টি। বিধিমালা ২০০৪ এ ১১০+ বিধি রয়েছে।",
}

class ChatRequest(BaseModel):
    question: str
    user_id: str = "anonymous"

class ChatResponse(BaseModel):
    answer: str
    references: List[str]
    cached: bool = False

@app.get("/")
def root():
    return {"status": "Somobay AI Backend Running - Full DB", "ain_chars": len(AIN_TEXT), "bidi_chars": len(BIDI_TEXT), "chunks": len(ALL_CHUNKS)}

@app.get("/health")
def health():
    return {"status": "ok", "chunks": len(ALL_CHUNKS)}

@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    q = req.question.strip()
    if not q:
        return ChatResponse(answer="অনুগ্রহ করে একটি প্রশ্ন করুন।", references=[], cached=False)
    
    cache_key = q.lower()
    if cache_key in CACHE:
        ans, refs = CACHE[cache_key]
        return ChatResponse(answer=ans, references=refs, cached=True)

    # Retrieve relevant chunks
    relevant = retrieve(q, top_k=4)
    
    if not relevant:
        ans = "দুঃখিত, এই বিষয়ে আইন ও বিধিমালায় সুনির্দিষ্ট তথ্য খুঁজে পাওয়া যায়নি। অনুগ্রহ করে আরও সুনির্দিষ্টভাবে প্রশ্ন করুন, যেমন ধারা নম্বর উল্লেখ করুন।"
        refs = []
        CACHE[cache_key] = (ans, refs)
        return ChatResponse(answer=ans, references=refs, cached=False)

    # Build answer from chunks
    # For short queries, combine chunks intelligently
    context_texts = [r["text"] for r in relevant]
    refs = list(set([f"{r['source']}" for r in relevant]))
    
    # Create answer: if query asks count, use meta
    lower_q = q.lower()
    answer_parts = []
    
    if ("কয়টি অধ্যায়" in q or "কতটি অধ্যায়" in q or "অধ্যায় ও কতটি ধারা" in q) :
        answer_parts.append(META_INFO["অধ্যায়"])
        answer_parts.append("\n\nপ্রাসঙ্গিক অংশ:")
    elif ("কতটি ধারা" in q and "আইনে" in q):
        answer_parts.append(META_INFO["ধারা"])
        answer_parts.append("\n\nপ্রাসঙ্গিক অংশ:")
    elif "অবসায়ন" in q or "অবসান" in q:
        answer_parts.append("সমবায় সমিতির অবসায়ন সংক্রান্ত বিধান আইনের ধারা ৫৪-৫৮ এবং বিধিমালার বিধি ৬৮-৭২ এ বর্ণিত আছে।")
    
    # Add retrieved context as answer (cleaned)
    for ct in context_texts[:2]:
        # trim to 600 chars for readability
        clean = ct[:800].strip()
        answer_parts.append(clean)
    
    final_answer = "\n\n".join(answer_parts)
    if len(final_answer) < 100:
        final_answer = "\n\n".join(context_texts)

    # Enhance references with page-like info
    detailed_refs = []
    for r in relevant[:3]:
        src = r["source"]
        snippet = r["text"][:80].replace("\n"," ").strip()
        detailed_refs.append(f"{src} - {snippet}...")

    CACHE[cache_key] = (final_answer, detailed_refs)
    return ChatResponse(answer=final_answer, references=detailed_refs, cached=False)

@app.post("/api/upload-law")
async def upload_law(file: UploadFile = File(...)):
    content = await file.read()
    try:
        text = content.decode('utf-8', errors='ignore')
    except:
        text = content.decode('latin-1', errors='ignore')
    
    # Add to knowledge base
    new_chunks = chunk_text(text)
    added = 0
    for c in new_chunks:
        ALL_CHUNKS.append({"text": c, "source": f"{file.filename}"})
        added += 1
    
    return {"message": "Indexed", "filename": file.filename, "chars": len(text), "new_chunks": added, "total_chunks": len(ALL_CHUNKS)}

# For backward compatibility
@app.post("/api/upload_law")
async def upload_law_underscore(file: UploadFile = File(...)):
    return await upload_law(file)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
