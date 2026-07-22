import os, re, pathlib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

app = FastAPI(title="Somobay AI - Universal Specific")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

BASE = pathlib.Path(__file__).parent
def load(p):
    try: return p.read_text(encoding='utf-8', errors='ignore') if p.exists() else ""
    except: return ""

AIN = load(BASE/"ain_2001.txt") or load(pathlib.Path("/mnt/data/ain_2001.txt"))
BIDI = load(BASE/"bidhimala_2004.txt") or load(pathlib.Path("/mnt/data/bidhimala_2004.txt"))
CIRC = load(BASE/"circular.txt")

def parse_index(text, max_len=6500):
    idx={}
    matches=list(re.finditer(r'\n\s*([০-৯0-9]+)[।]\s*([^\n]{3,150})\n', text))
    for i,m in enumerate(matches):
        num_en = m.group(1).translate(str.maketrans("০১২৩৪৫৬৭৮৯","0123456789"))
        start=m.start()
        end=matches[i+1].start() if i+1 < len(matches) else start+max_len
        content=text[start:end].strip()[:max_len]
        if len(content)>120:
            idx[num_en] = {"title": m.group(2).strip(), "content": content, "num_bn": m.group(1)}
    return idx

AIN_IDX = parse_index(AIN, 7000)
BIDI_IDX = parse_index(BIDI, 5000)

print(f"Ain {len(AIN_IDX)} Bidi {len(BIDI_IDX)}")

def make_chunks(text, source):
    chunks=[]; paras=re.split(r'\n\s*\n', text); buf=""
    for para in paras:
        para=para.strip()
        if len(para)<40: continue
        if re.match(r'^[০-৯0-9]+[।]', para) and len(buf)>400:
            chunks.append({"text": buf, "source": source}); buf=para
        else:
            buf += "\n\n" + para
            if len(buf)>1300:
                chunks.append({"text": buf, "source": source}); buf=""
    if buf: chunks.append({"text": buf, "source": source})
    return chunks

ALL_CHUNKS = make_chunks(AIN, "আইন ২০০১") + make_chunks(BIDI, "বিধিমালা ২০০৪")
if CIRC: ALL_CHUNKS += make_chunks(CIRC, "সার্কুলার")

def retrieve(query, k=3):
    trans=str.maketrans("০১২৩৪৫৬৭৮৯","0123456789")
    nums_en=[n.translate(trans) for n in re.findall(r'[০-৯0-9]+', query)]
    # Direct dhara fetch
    if nums_en:
        for n in nums_en:
            if n in AIN_IDX:
                return [{"text": AIN_IDX[n]["content"], "source": f"ধারা {n}"},]
        # If multiple numbers, return them
        res=[]
        for n in nums_en[:2]:
            if n in AIN_IDX: res.append({"text": AIN_IDX[n]["content"], "source": f"ধারা {n}"})
            if n in BIDI_IDX: res.append({"text": BIDI_IDX[n]["content"], "source": f"বিধি {n}"})
        if res: return res

    # Keyword
    q_tokens=set(re.findall(r'[\u0980-\u09FF]+', query))
    stop=set(["কি","কত","কোন","এবং","হবে","আছে","করে","থেকে","জন্য","এই","সে","যে","এর","এ","ও","টা","টি","হয়","কয়টি","হচ্ছে","হলে","সমিতির","সমিতি","সমবায়","আইনে"])
    q_f=[t for t in q_tokens if t not in stop and len(t)>2]
    scored=[]
    for idx,ch in enumerate(ALL_CHUNKS):
        score=sum(1 for qt in q_f if qt in ch["text"])
        # Bonus for title match
        if score>0: scored.append((score, idx))
    scored.sort(reverse=True)
    return [ALL_CHUNKS[i] for _,i in scored[:k]]

GROQ_KEY=os.environ.get("GROQ_API_KEY","")
groq_client=None
if GROQ_KEY:
    try:
        from groq import Groq
        groq_client=Groq(api_key=GROQ_KEY)
    except: pass

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
    return {"status":"Universal Specific", "groq": groq_client is not None, "ain": len(AIN_IDX)}

@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    q=req.question.strip()
    if not q:
        return ChatResponse(answer="প্রশ্ন লিখুন", references=[], cached=False)
    key=q.lower()
    if key in CACHE:
        a,_=CACHE[key]
        return ChatResponse(answer=a, references=[], cached=True)

    # Meta
    if "অধ্যায়" in q and "ধারা" in q:
        ans="সমবায় সমিতি আইন, ২০০১ এ মোট ১৩টি অধ্যায় এবং ৯০টি ধারা রয়েছে (মূল গেজেট অনুযায়ী, বর্তমানে ৮৮টি কার্যকর)। বিধিমালা ২০০৪ এ ১১৭টি বিধি রয়েছে।\n\nসূত্র: আইন ২০০১ ভূমিকা, ধারা ১-৯০, বিধি ১-১১৭"
        CACHE[key]=(ans,[]); return ChatResponse(answer=ans, references=[], cached=False)

    relevant=retrieve(q)
    if not relevant:
        ans=f"'{q}' বিষয়ে আইনে সরাসরি তথ্য পাওয়া যায়নি। ধারা নম্বর দিয়ে জিজ্ঞাসা করুন।\n\nসূত্র: -"
        CACHE[key]=(ans,[]); return ChatResponse(answer=ans, references=[], cached=False)

    context="\n\n---\n\n".join([r["text"][:2500] for r in relevant[:2]])

    if groq_client:
        try:
            system_prompt = """তুমি বাংলাদেশের সমবায় আইন ২০০১ ও বিধিমালা ২০০৪ এর নির্ভরযোগ্য বিশেষজ্ঞ। তোমার উত্তর সবসময় এই ফরম্যাটে হবে:

ফরম্যাট (৩টি অংশ):

১. প্রথম লাইন: সুনির্দিষ্ট সরাসরি উত্তর। যেমন:
- "এডহক (অন্তর্বর্তী) কমিটির মেয়াদ ১২০ দিন।"
- "ব্যবস্থাপনা কমিটির মেয়াদ ৩ বছর।"
- "সদস্য হতে হলে বয়স ২১ বছর হতে হবে।"
এই লাইনের শেষে ছোট করে (ধারা ১৮(৫)) এর মতো উল্লেখ করো।

২. মাঝের ৩-৪ বাক্য: আইনের প্রাসঙ্গিক উপ-ধারাগুলো (যেমন ১৮(৩), ১৮(৪), ১৮(৫), ১৮(৭)) ব্যাখ্যা করো। কেন এই নিয়ম, কখন প্রযোজ্য, কি করতে হয় - মানুষ যেন বুঝতে পারে। অসম্পূর্ণ রাখবে না।

৩. শেষ লাইন: "সূত্র: ধারা ১৮(৫), ১৮(৭)" - এই ফরম্যাটে।

নিয়ম:
- শুধু Context থেকে উত্তর দেবে, বানাবে না
- বাংলায়, সহজ, মানবিক ভাষায়
- প্রতিটি প্রশ্নের জন্য এই ৩-অংশের ফরম্যাট মেনে চলবে
- ১২০ দিন, ৩ বছর, ৩০ দিন, ২১ বছর - সংখ্যাগুলো নির্ভুল হতে হবে
- কোনো হলুদ বক্স বা আলাদা রেফারেন্স লিস্ট দেবে না, শুধু inline (ধারা X) এবং শেষে সূত্র লাইন
"""

            user_prompt = f"""Context (আইনের হুবহু অংশ):
{context[:9000]}

প্রশ্ন: {q}

উপরের ফরম্যাটে (সুনির্দিষ্ট উত্তর + বিস্তারিত ব্যাখ্যা + সূত্র) উত্তর দাও:"""

            comp=groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role":"system","content":system_prompt},
                    {"role":"user","content":user_prompt}
                ],
                temperature=0.08,
                max_tokens=800,
            )
            final=comp.choices[0].message.content.strip()
            CACHE[key]=(final,[])
            return ChatResponse(answer=final, references=[], cached=False)
        except Exception as e:
            print(f"Groq error: {e}")

    # Fallback
    ans=relevant[0]["text"][:1500] + "\n\nসূত্র: ধারা ১৮"
    CACHE[key]=(ans,[]); return ChatResponse(answer=ans, references=[], cached=False)
