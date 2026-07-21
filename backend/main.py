import os, re, pathlib
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

app = FastAPI(title="Somobay AI - Groq Powered")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

BASE = pathlib.Path(__file__).parent
def load_txt(p):
    try:
        return p.read_text(encoding='utf-8', errors='ignore') if p.exists() else ""
    except:
        return ""

AIN = load_txt(BASE/"ain_2001.txt")
BIDI = load_txt(BASE/"bidhimala_2004.txt")
# Fallback for local dev
if len(AIN)<1000:
    AIN = load_txt(pathlib.Path("/mnt/data/ain_2001.txt"))
if len(BIDI)<1000:
    BIDI = load_txt(pathlib.Path("/mnt/data/bidhimala_2004.txt"))

print(f"Loaded AIN {len(AIN)} chars, BIDI {len(BIDI)} chars")

# Chunking for RAG
def chunk_text(text, size=1000, overlap=200):
    chunks=[]
    paras = re.split(r'\n\s*\n', text)
    for para in paras:
        para=para.strip()
        if len(para)<60: continue
        if len(para)<=size:
            chunks.append(para)
        else:
            for i in range(0,len(para), size-overlap):
                c=para[i:i+size]
                if len(c)>80:
                    chunks.append(c)
    return chunks

AIN_CHUNKS = chunk_text(AIN)
BIDI_CHUNKS = chunk_text(BIDI)
ALL = [{"text": c, "src": "সমবায় সমিতি আইন, ২০০১"} for c in AIN_CHUNKS] + [{"text": c, "src": "সমবায় সমিতি বিধিমালা, ২০০৪"} for c in BIDI_CHUNKS]

def tokenize(s):
    return re.findall(r'[\u0980-\u09FFa-zA-Z0-9]+', s.lower())

def retrieve(query, k=5):
    q_tokens = set(tokenize(query))
    scored=[]
    for idx,ch in enumerate(ALL):
        c_tokens = set(tokenize(ch["text"]))
        overlap = len(q_tokens & c_tokens)
        # Bonus for dhara mention
        bonus=0
        m = re.search(r'(\d+)[\s]*নং', query)
        if m and m.group(1) in ch["text"]:
            bonus+=2
        if overlap>0:
            scored.append((overlap+bonus, idx))
    scored.sort(reverse=True, key=lambda x:x[0])
    top_idx = [i for sc,i in scored[:k] if sc>=1]
    results = [ALL[i] for i in top_idx]
    # If no good match, return empty to avoid hallucination
    if not results or scored[0][0] < 2:
        return []
    return results

# Groq client
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
groq_client = None
if GROQ_KEY:
    try:
        from groq import Groq
        groq_client = Groq(api_key=GROQ_KEY)
        print("Groq client initialized")
    except Exception as e:
        print(f"Groq init failed: {e}")
        groq_client=None

CACHE={}

class ChatRequest(BaseModel):
    question: str
    user_id: str="anon"
class ChatResponse(BaseModel):
    answer: str
    references: List[str]
    cached: bool=False

@app.get("/")
def root():
    return {"status":"Somobay AI Groq Running", "groq_enabled": groq_client is not None, "chunks": len(ALL), "ain": len(AIN), "bidi": len(BIDI)}

@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    q = req.question.strip()
    if not q:
        return ChatResponse(answer="অনুগ্রহ করে প্রশ্ন লিখুন।", references=[], cached=False)
    
    key=q.lower()
    if key in CACHE:
        a,r=CACHE[key]
        return ChatResponse(answer=a, references=r, cached=True)

    relevant = retrieve(q, k=5)
    
    if not relevant:
        ans = "দুঃখিত, আপনার প্রশ্নের সাথে সম্পর্কিত সুনির্দিষ্ট তথ্য সমবায় আইন ২০০১ ও বিধিমালা ২০০৪ এ খুঁজে পাওয়া যায়নি। অনুগ্রহ করে ধারা বা বিধি নম্বর উল্লেখ করে আরও সুনির্দিষ্টভাবে প্রশ্ন করুন। যেমন: 'ব্যবস্থাপনা কমিটি গঠন - ধারা ১৮ অনুযায়ী কী বলা আছে?'"
        refs=[]
        CACHE[key]=(ans,refs)
        return ChatResponse(answer=ans, references=refs, cached=False)

    context_str = "\n\n---\n\n".join([f"[{r['src']}]\n{r['text'][:1200]}" for r in relevant[:4]])
    refs = [f"{r['src']}: {r['text'][:100].replace(chr(10),' ')}..." for r in relevant[:3]]

    # If Groq available, use LLM
    if groq_client:
        try:
            prompt = f"""তুমি সমবায় আইন বিশেষজ্ঞ 'সমবায় আইন AI'। তোমার কাজ শুধুমাত্র নিচে দেওয়া আইন ও বিধিমালার প্রসঙ্গ (Context) থেকে উত্তর দেওয়া।

নিয়ম:
1. শুধুমাত্র Context থেকে উত্তর দেবে। বাইরে থেকে বানিয়ে কিছু বলবে না।
2. উত্তর অবশ্যই বাংলায় দেবে, সহজ ও নির্ভরযোগ্য ভাষায়।
3. উত্তরের শেষে অবশ্যই কোন ধারা/বিধি থেকে উত্তর দিয়েছো তা উল্লেখ করবে।
4. যদি Context এ উত্তর না থাকে, তাহলে বলবে "এই বিষয়ে প্রসঙ্গে তথ্য নেই"।
5. ভুল বা অনুমান করে উত্তর দেবে না। নির্ভুলতাই তোমার প্রধান লক্ষ্য।

Context:
{context_str}

প্রশ্ন: {q}

উত্তর (বাংলায়, রেফারেন্সসহ):"""

            completion = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "তুমি বাংলাদেশের সমবায় আইন ২০০১ ও বিধিমালা ২০০৪ এর নির্ভরযোগ্য বিশেষজ্ঞ। শুধু প্রদত্ত Context থেকে নির্ভুল উত্তর দাও।"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1000,
            )
            llm_answer = completion.choices[0].message.content.strip()
            CACHE[key]=(llm_answer, refs)
            return ChatResponse(answer=llm_answer, references=refs, cached=False)
        except Exception as e:
            print(f"Groq error: {e}")
            # fallback to extractive
            pass

    # Fallback extractive (no LLM)
    fallback_ans = "\n\n".join([r["text"][:800] for r in relevant[:2]])
    CACHE[key]=(fallback_ans, refs)
    return ChatResponse(answer=fallback_ans, references=refs, cached=False)

@app.post("/api/upload-law")
async def upload_law(file: UploadFile = File(...)):
    content = await file.read()
    txt = content.decode('utf-8', errors='ignore')
    return {"chars": len(txt), "filename": file.filename}
