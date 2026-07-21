import os, re, pathlib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

app = FastAPI(title="Somobay AI - Full Book Reader")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

BASE = pathlib.Path(__file__).parent
def load(p):
    try:
        return p.read_text(encoding='utf-8', errors='ignore') if p.exists() else ""
    except:
        return ""

AIN = load(BASE/"ain_2001.txt")
BIDI = load(BASE/"bidhimala_2004.txt")
CIRC = load(BASE/"circular.txt")

# fallback local
if len(AIN)<1000:
    AIN = load(pathlib.Path("/mnt/data/ain_2001.txt"))
if len(BIDI)<1000:
    BIDI = load(pathlib.Path("/mnt/data/bidhimala_2004.txt"))

print(f"Books loaded - Ain: {len(AIN)}, Bidi: {len(BIDI)}, Circular: {len(CIRC)}")

# Smart chunking - keep dhara together
def make_chunks(text, source):
    chunks=[]
    # split by double newline but keep dhara numbers
    paras = re.split(r'\n\s*\n', text)
    buf=""
    for para in paras:
        para=para.strip()
        if len(para)<40: continue
        # If para starts with dhara number, flush previous buf
        if re.match(r'^[০-৯0-9]+[।]', para) and len(buf)>300:
            chunks.append({"text": buf, "source": source})
            buf=para
        else:
            buf += "\n\n" + para
            if len(buf) > 1200:
                chunks.append({"text": buf, "source": source})
                buf=""
    if buf:
        chunks.append({"text": buf, "source": source})
    return chunks

ALL_CHUNKS = []
ALL_CHUNKS += make_chunks(AIN, "সমবায় সমিতি আইন ২০০১")
ALL_CHUNKS += make_chunks(BIDI, "সমবায় সমিতি বিধিমালা ২০০৪")
if CIRC:
    ALL_CHUNKS += make_chunks(CIRC, "সার্কুলার")

print(f"Total chunks: {len(ALL_CHUNKS)}")

def tokenize(s):
    return re.findall(r'[\u0980-\u09FFa-zA-Z0-9]+', s.lower())

# BM25 like scoring - full book search
def retrieve_fullbook(query, k=6):
    q_tokens = tokenize(query)
    if not q_tokens:
        return []
    # remove very common stop words
    stop = set(["কি","কত","কোন","এবং","হবে","আছে","করে","থেকে","জন্য","এই","সে","যে","এর","এ","ও","টা","টি"])
    q_filtered = [t for t in q_tokens if t not in stop and len(t)>1]
    if not q_filtered:
        q_filtered = q_tokens

    scored=[]
    for idx,ch in enumerate(ALL_CHUNKS):
        txt = ch["text"]
        c_tokens = tokenize(txt)
        # TF scoring
        score=0
        for qt in q_filtered:
            cnt = c_tokens.count(qt)
            if cnt>0:
                score += cnt * (2 if len(qt)>3 else 1)
        # Bonus for exact phrase
        for qt in q_filtered:
            if qt in txt.lower():
                score += 0.5
        # Bonus if query asks about specific topic and chunk contains it
        if score>0:
            scored.append((score, idx))
    scored.sort(reverse=True, key=lambda x:x[0])
    # Take top k with score > threshold
    top = [ALL_CHUNKS[i] for sc,i in scored[:k] if sc>=1.5]
    # If still low, take at least 2 top to give LLM some context
    if len(top)<2 and scored:
        top = [ALL_CHUNKS[i] for sc,i in scored[:2]]
    return top

GROQ_KEY = os.environ.get("GROQ_API_KEY","")
groq_client=None
if GROQ_KEY:
    try:
        from groq import Groq
        groq_client = Groq(api_key=GROQ_KEY)
    except Exception as e:
        print(f"Groq init error {e}")

CACHE={}

class ChatRequest(BaseModel):
    question: str
    user_id: str="anon"
class ChatResponse(BaseModel):
    answer: str
    references: List[str] = []  # Keep empty as user requested no separate ref box
    cached: bool=False

@app.get("/")
def root():
    return {"status":"Full Book Reader", "chunks": len(ALL_CHUNKS), "groq": groq_client is not None, "books": {"ain": len(AIN), "bidi": len(BIDI), "circular": len(CIRC)}}

@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    q = req.question.strip()
    if not q:
        return ChatResponse(answer="অনুগ্রহ করে প্রশ্ন লিখুন।", references=[], cached=False)
    
    key = q.lower()
    if key in CACHE:
        a,_ = CACHE[key]
        return ChatResponse(answer=a, references=[], cached=True)

    relevant = retrieve_fullbook(q, k=6)
    
    if not relevant:
        # Even if no chunk, let LLM try with general instruction if available
        if groq_client:
            try:
                prompt = f"""তুমি বাংলাদেশের সমবায় আইন বিশেষজ্ঞ। ব্যবহারকারী প্রশ্ন করেছে কিন্তু প্রদত্ত বইতে সরাসরি মিল পাওয়া যায়নি।

প্রশ্ন: {q}

তুমি তোমার জ্ঞান থেকে উত্তর দেবে না। বরং বলবে:
"দুঃখিত, সমবায় আইন ২০০১, বিধিমালা ২০০৪ ও সার্কুলারে এই বিষয়ে সরাসরি তথ্য খুঁজে পাওয়া যায়নি। অনুগ্রহ করে ধারা নম্বর বা আরও সুনির্দিষ্ট শব্দ দিয়ে প্রশ্ন করুন।"

উত্তরটি বাংলায় দাও।
"""
                comp = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role":"user","content":prompt}],
                    temperature=0.2,
                    max_tokens=300,
                )
                ans = comp.choices[0].message.content.strip()
                CACHE[key]=(ans,[])
                return ChatResponse(answer=ans, references=[], cached=False)
            except:
                pass
        ans = "দুঃখিত, এই বিষয়ে আইন ও বিধিমালায় সুনির্দিষ্ট তথ্য খুঁজে পাওয়া যায়নি। ধারা নম্বর উল্লেখ করে আবার জিজ্ঞাসা করুন।"
        CACHE[key]=(ans,[])
        return ChatResponse(answer=ans, references=[], cached=False)

    # Build full context from all 3 books
    context_parts=[]
    for r in relevant[:6]:
        context_parts.append(f"[{r['source']}]\n{r['text'][:1500]}")
    full_context = "\n\n---\n\n".join(context_parts)

    if groq_client:
        try:
            system_prompt = """তুমি 'সমবায় আইন AI' - বাংলাদেশের সমবায় সমিতি আইন ২০০১, বিধিমালা ২০০৪ এবং সকল সার্কুলারের উপর প্রশিক্ষিত নির্ভরযোগ্য বিশেষজ্ঞ।

তোমার কাজ:
1. ব্যবহারকারী যেভাবেই প্রশ্ন করুক (সাধারণ ভাষায়, ভুল বানানে, বাক্যে), তুমি পুরো বইগুলো থেকে প্রাসঙ্গিক অংশ পড়ে বুঝে উত্তর দেবে।
2. উত্তর ১০০% নির্ভুল হতে হবে, বইয়ের বাইরে থেকে বানিয়ে কিছু বলবে না।
3. উত্তর বাংলায়, সহজ, মানবিক, এবং পূর্ণাঙ্গভাবে দেবে যাতে ব্যবহারকারী সন্তুষ্ট হয়।
4. উত্তরের মধ্যেই inline রেফারেন্স উল্লেখ করবে যেমন: '... (ধারা ১৮, আইন ২০০১)' বা '(বিধি ২৩, বিধিমালা ২০০৪)'। আলাদা রেফারেন্স লিস্ট দেবে না।
5. যদি একাধিক ধারা প্রাসঙ্গিক হয়, সবগুলো গুছিয়ে ব্যাখ্যা করো।
6. উত্তর সংক্ষিপ্ত নয়, পরিপূর্ণ ব্যাখ্যা দাও।"""

            user_prompt = f"""নিচে সমবায় আইন, বিধিমালা ও সার্কুলার থেকে প্রাসঙ্গিক অংশ দেওয়া হলো। এগুলো ভালোভাবে পড়ে প্রশ্নের উত্তর দাও।

প্রসঙ্গ (৩টি বই থেকে):
{full_context[:9000]}

প্রশ্ন: {q}

উত্তর (বাংলায়, inline ধারা উল্লেখসহ, বিস্তারিত ও নির্ভুলভাবে):"""

            comp = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role":"system","content": system_prompt},
                    {"role":"user","content": user_prompt}
                ],
                temperature=0.15,
                max_tokens=1500,
            )
            final_ans = comp.choices[0].message.content.strip()
            CACHE[key]=(final_ans, [])
            return ChatResponse(answer=final_ans, references=[], cached=False)
        except Exception as e:
            print(f"Groq error: {e}")
            # fallback to direct context display
            fallback = "\n\n".join([r["text"][:1000] for r in relevant[:2]])
            CACHE[key]=(fallback, [])
            return ChatResponse(answer=fallback, references=[], cached=False)
    else:
        # No Groq - return best chunks directly
        ans = "\n\n".join([f"{r['text'][:1000]}\n({r['source']})" for r in relevant[:2]])
        CACHE[key]=(ans, [])
        return ChatResponse(answer=ans, references=[], cached=False)
