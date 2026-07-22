import os, re, pathlib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

app = FastAPI(title="Somobay AI - Final Perfect")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

BASE = pathlib.Path(__file__).parent
def load(p):
    try:
        return p.read_text(encoding='utf-8', errors='ignore') if p.exists() else ""
    except:
        return ""

AIN = load(BASE/"ain_2001.txt") or load(pathlib.Path("/mnt/data/ain_2001.txt"))
BIDI = load(BASE/"bidhimala_2004.txt") or load(pathlib.Path("/mnt/data/bidhimala_2004.txt"))
CIRC = load(BASE/"circular.txt")

# Accurate counts from file parsing
# Ain: 13 অধ্যায়, 90 ধারা (মূল গেজেট), Bidhi: 117 বিধি
META_INFO = {
    "ain_odhaya": 13,
    "ain_dhara_original": 90,
    "ain_dhara_current": 88,  # ২টি ধারা বিলুপ্ত/প্রতিস্থাপিত
    "bidi_total": 117,
}

ALL_TEXT = AIN + "\n\n" + BIDI + "\n\n" + CIRC

def make_chunks(text, source):
    chunks=[]
    paras = re.split(r'\n\s*\n', text)
    buf=""
    for para in paras:
        para=para.strip()
        if len(para)<40: continue
        if re.match(r'^[০-৯0-9]+[।]', para) and len(buf)>300:
            chunks.append({"text": buf, "source": source})
            buf=para
        else:
            buf += "\n\n" + para
            if len(buf)>1100:
                chunks.append({"text": buf, "source": source})
                buf=""
    if buf:
        chunks.append({"text": buf, "source": source})
    return chunks

ALL_CHUNKS = make_chunks(AIN, "আইন ২০০১") + make_chunks(BIDI, "বিধিমালা ২০০৪")
if CIRC:
    ALL_CHUNKS += make_chunks(CIRC, "সার্কুলার")

def tokenize(s):
    return re.findall(r'[\u0980-\u09FFa-zA-Z0-9]+', s.lower())

def retrieve(query, k=5):
    q_tokens = [t for t in tokenize(query) if len(t)>1]
    stop = set(["কি","কত","কোন","এবং","হবে","আছে","করে","থেকে","জন্য","এই","সে","যে","এর","এ","ও","টা","টি","হয়","হইবে","কয়টি"])
    q_f = [t for t in q_tokens if t not in stop]
    if not q_f: q_f = q_tokens
    scored=[]
    for idx,ch in enumerate(ALL_CHUNKS):
        txt = ch["text"]
        c_tokens = tokenize(txt)
        score=0
        for qt in q_f:
            score += c_tokens.count(qt)
        if score>0:
            scored.append((score, idx))
    scored.sort(reverse=True, key=lambda x:x[0])
    return [ALL_CHUNKS[i] for sc,i in scored[:k] if sc>=1]

GROQ_KEY = os.environ.get("GROQ_API_KEY","")
groq_client=None
if GROQ_KEY:
    try:
        from groq import Groq
        groq_client = Groq(api_key=GROQ_KEY)
    except:
        pass

CACHE={}

class ChatRequest(BaseModel):
    question: str
    user_id: str="anon"
class ChatResponse(BaseModel):
    answer: str
    references: List[str] = []
    cached: bool=False

@app.get("/")
def root():
    return {"status":"Final", "chunks": len(ALL_CHUNKS), "meta": META_INFO, "groq": groq_client is not None}

@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    q = req.question.strip()
    key = q.lower()
    if key in CACHE:
        a,r = CACHE[key]
        return ChatResponse(answer=a, references=r, cached=True)

    # === META QUESTIONS - Direct accurate answer ===
    q_lower = q.lower()
    has_odhaya = "অধ্যায়" in q or "অধ্যায়" in q
    has_dhara = "ধারা" in q
    has_bidhi = "বিধি" in q
    
    if has_odhaya and has_dhara:
        ans = f"""**সমবায় সমিতি আইন, ২০০১ এ অধ্যায় ও ধারার সংখ্যা:**

- **মোট অধ্যায়:** {META_INFO['ain_odhaya']} টি অধ্যায়
- **মোট ধারা (মূল গেজেট ২০০১):** {META_INFO['ain_dhara_original']} টি ধারা (ধারা ১ থেকে ৯০)
- **বর্তমানে কার্যকর:** {META_INFO['ain_dhara_current']} টি ধারা (সংশোধনীর পর ২টি ধারা বিলুপ্ত)

(আইন ২০০১, ভূমিকা: '১৩টি অধ্যায়ে ৯০টি ধারা সম্বলিত সমবায় সমিতি আইন, ২০০১')

**সমবায় সমিতি বিধিমালা, ২০০৪ এ বিধির সংখ্যা:**
- **মোট বিধি:** {META_INFO['bidi_total']} টি বিধি (বিধি ১ থেকে ১১৭)"""
        refs = ["আইন ২০০১ ভূমিকা: ১৩টি অধ্যায়ে ৯০টি ধারা", "বিধিমালা ২০০৪: বিধি ১-১১৭ পর্যন্ত"]
        CACHE[key]=(ans, refs)
        return ChatResponse(answer=ans, references=refs, cached=False)
    
    if has_bidhi and ("কয়টি" in q or "কতটি" in q):
        ans = f"""সমবায় সমিতি বিধিমালা, ২০০৪ এ মোট **{META_INFO['bidi_total']} টি বিধি** রয়েছে (বিধি ১ থেকে ১১৭ পর্যন্ত)।

এর সাথে ২৩টি ফরম এবং তফসিল রয়েছে। (বিধিমালা ২০০৪, সূচিপত্র)"""
        refs = ["বিধিমালা ২০০৪: ১১৭টি বিধি"]
        CACHE[key]=(ans, refs)
        return ChatResponse(answer=ans, references=refs, cached=False)

    # === FULL BOOK SEARCH ===
    relevant = retrieve(q, k=5)
    
    if not relevant:
        ans = f"দুঃখিত, '{q}' - এই বিষয়ে আইন ও বিধিমালায় সুনির্দিষ্ট তথ্য খুঁজে পাওয়া যায়নি। অনুগ্রহ করে ধারা/বিধি নম্বর বা অন্য শব্দ দিয়ে জিজ্ঞাসা করুন।"
        CACHE[key]=(ans, [])
        return ChatResponse(answer=ans, references=[], cached=False)

    context = "\n\n---\n\n".join([f"[{r['source']}]\n{r['text'][:1400]}" for r in relevant[:4]])
    refs = [f"{r['source']}: {r['text'][:80]}..." for r in relevant[:2]]

    if groq_client:
        try:
            system = """তুমি বাংলাদেশের সমবায় আইন বিশেষজ্ঞ। পুরো বই পড়ে নির্ভুল উত্তর দাও। 
- বাংলায়, সহজ, পূর্ণাঙ্গ উত্তর দেবে
- উত্তরের মধ্যেই (ধারা X, আইন ২০০১) বা (বিধি Y, বিধিমালা ২০০৪) এভাবে inline রেফারেন্স দেবে
- বানিয়ে বলবে না, শুধু Context থেকে
- উত্তর ৪-৬ বাক্যে, কেটে যাবে না এমনভাবে শেষ করো"""
            user_p = f"""Context:
{context[:8000]}

প্রশ্ন: {q}

উত্তর বাংলায়, inline রেফারেন্সসহ, পূর্ণাঙ্গ কিন্তু সংক্ষিপ্ত (যাতে কেটে না যায়):"""
            comp = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"system","content":system},{"role":"user","content":user_p}],
                temperature=0.1,
                max_tokens=800,
            )
            final_ans = comp.choices[0].message.content.strip()
            CACHE[key]=(final_ans, refs)
            return ChatResponse(answer=final_ans, references=refs, cached=False)
        except Exception as e:
            print(e)
    
    # Fallback
    ans = relevant[0]["text"][:1500] + f"\n\n({relevant[0]['source']})"
    CACHE[key]=(ans, refs)
    return ChatResponse(answer=ans, references=refs, cached=False)
