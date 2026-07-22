import os, re, pathlib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

app = FastAPI(title="Somobay AI - Specific Answer No Ref")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

BASE = pathlib.Path(__file__).parent
def load(p):
    try: return p.read_text(encoding='utf-8', errors='ignore') if p.exists() else ""
    except: return ""

AIN = load(BASE/"ain_2001.txt") or load(pathlib.Path("/mnt/data/ain_2001.txt"))
BIDI = load(BASE/"bidhimala_2004.txt") or load(pathlib.Path("/mnt/data/bidhimala_2004.txt"))
CIRC = load(BASE/"circular.txt")

# Build dhara wise index for accurate specific answers
def parse_dhara_index(text):
    idx={}
    pattern = r'\n\s*([০-৯0-9]+)[।]\s*([^\n]{3,120})\n'
    matches=list(re.finditer(pattern, text))
    for i,m in enumerate(matches):
        num_en = m.group(1).translate(str.maketrans("০১২৩৪৫৬৭৮৯","0123456789"))
        title = m.group(2).strip()
        start=m.start()
        end=matches[i+1].start() if i+1 < len(matches) else start+4000
        content=text[start:end].strip()[:3500]
        if len(content)>150:
            idx[num_en] = {"title": title, "content": content, "num_bn": m.group(1)}
    return idx

AIN_IDX = parse_dhara_index(AIN)
BIDI_IDX = parse_dhara_index(BIDI)

print(f"Ain indexed: {len(AIN_IDX)}, Bidi indexed: {len(BIDI_IDX)}")

# Topic to Dhara mapping for specific questions
TOPIC_MAP = {
    "মেয়াদ": ["18", "১৮"],
    "মেয়াদ": ["18", "১৮"],
    "পদ শূন্য": ["20", "২0"],
    "শূন্য হলে": ["20", "২০"],
    "যোগ্যতা": ["19", "১৯"],
    "অযোগ্যতা": ["19", "১৯"],
    "বিরোধ": ["50", "৫০"],
    "বিবাদ": ["50", "৫০"],
    "সদস্য পদ বাতিল": ["17", "১৭"],
    "ঋণ খেলাপি": ["19", "৮৭"],
    "সভা না করলে": ["22", "২২"],
    "সভা": ["22", "২২", "23", "২৩"],
}

def make_chunks(text, source):
    chunks=[]
    paras=re.split(r'\n\s*\n', text)
    buf=""
    for para in paras:
        para=para.strip()
        if len(para)<40: continue
        if re.match(r'^[০-৯0-9]+[।]', para) and len(buf)>300:
            chunks.append({"text": buf, "source": source}); buf=para
        else:
            buf += "\n\n" + para
            if len(buf)>1200:
                chunks.append({"text": buf, "source": source}); buf=""
    if buf: chunks.append({"text": buf, "source": source})
    return chunks

ALL_CHUNKS = make_chunks(AIN, "আইন ২০০১") + make_chunks(BIDI, "বিধিমালা ২০০৪")
if CIRC: ALL_CHUNKS += make_chunks(CIRC, "সার্কুলার")

def retrieve_specific(query, k=4):
    q=query.lower()
    # 1. Check if query contains number like 50 ধারা
    nums = re.findall(r'[০-৯0-9]+', query)
    # Convert bn to en
    trans=str.maketrans("০১২৩৪৫৬৭৮৯","0123456789")
    nums_en=[n.translate(trans) for n in nums]
    
    results=[]
    # If number mentioned, directly fetch that dhara
    for n in nums_en:
        if n in AIN_IDX:
            results.append(AIN_IDX[n]["content"])
        if n in BIDI_IDX:
            results.append(BIDI_IDX[n]["content"])
    
    if results:
        # Return exact dhara contents as chunks
        return [{"text": r, "source": "নির্দিষ্ট ধারা"} for r in results[:2]]

    # 2. Topic mapping
    for topic, dharas in TOPIC_MAP.items():
        if topic in query:
            for d in dharas:
                d_en = d.translate(trans) if any(c in "০১২৩৪৫৬৭৮৯" for c in d) else d
                if d_en in AIN_IDX:
                    results.append(AIN_IDX[d_en]["content"])
            if results:
                return [{"text": r, "source": f"বিষয়: {topic}"} for r in results[:2]]

    # 3. General keyword search
    q_tokens=set(re.findall(r'[\u0980-\u09FFa-zA-Z0-9]+', q))
    stop=set(["কি","কত","কোন","এবং","হবে","আছে","করে","থেকে","জন্য","এই","সে","যে","এর","এ","ও","টা","টি","হয়","কয়টি","বলুন","দিন"])
    q_f=[t for t in q_tokens if t not in stop and len(t)>1]
    scored=[]
    for idx,ch in enumerate(ALL_CHUNKS):
        txt=ch["text"]
        score=sum(1 for qt in q_f if qt in txt.lower())
        if score>0: scored.append((score, idx))
    scored.sort(reverse=True, key=lambda x:x[0])
    top=[ALL_CHUNKS[i] for sc,i in scored[:k] if sc>=1]
    return top

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
    references: List[str] = []  # Always empty - no yellow box
    cached: bool=False

@app.get("/")
def root():
    return {"status":"Specific No Ref", "ain": len(AIN_IDX), "bidi": len(BIDI_IDX), "groq": groq_client is not None}

@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    q=req.question.strip()
    key=q.lower()
    if key in CACHE:
        a,_=CACHE[key]
        return ChatResponse(answer=a, references=[], cached=True)

    # Meta count
    if "অধ্যায়" in q and "ধারা" in q:
        ans="সমবায় সমিতি আইন, ২০০১ এ মোট ১৩টি অধ্যায় এবং ৯০টি ধারা রয়েছে (মূল গেজেট অনুযায়ী, বর্তমানে ৮৮টি কার্যকর)। বিধিমালা ২০০৪ এ ১১৭টি বিধি রয়েছে।"
        CACHE[key]=(ans,[]); return ChatResponse(answer=ans, references=[], cached=False)
    if "বিধি" in q and "কয়টি" in q:
        ans="সমবায় সমিতি বিধিমালা, ২০০৪ এ মোট ১১৭টি বিধি রয়েছে।"
        CACHE[key]=(ans,[]); return ChatResponse(answer=ans, references=[], cached=False)

    relevant=retrieve_specific(q, k=3)
    
    if not relevant:
        ans=f"'{q}' বিষয়ে আইন ও বিধিমালায় সরাসরি তথ্য পাওয়া যায়নি। ধারা নম্বর দিয়ে জিজ্ঞাসা করুন, যেমন 'ধারা ৫০ কি'।"
        CACHE[key]=(ans,[]); return ChatResponse(answer=ans, references=[], cached=False)

    context="\n\n---\n\n".join([r["text"][:1600] for r in relevant[:2]])

    if groq_client:
        try:
            system="""তুমি সমবায় আইন বিশেষজ্ঞ। তোমার কাজ সুনির্দিষ্ট, নির্ভুল উত্তর দেওয়া।

নিয়ম:
1. প্রথম লাইনেই প্রশ্নের সুনির্দিষ্ট উত্তর দাও (যেমন: মেয়াদ ৩ বছর, পদ শূন্য হলে ৩০ দিনের মধ্যে পূরণ করতে হবে)।
2. তারপর ২-৩ বাক্যে আইনের ভাষায় ব্যাখ্যা দাও।
3. উত্তর বাংলায়, সহজ, কিন্তু আইনের মতো নির্ভুল।
4. কোনো রেফারেন্স লিস্ট বা হলুদ বক্স দেবে না, উত্তরের মধ্যেই ছোট করে (ধারা ১৮) এভাবে উল্লেখ করো।
5. বানিয়ে বলবে না, শুধু Context থেকে।
6. উত্তর ১২০ শব্দের মধ্যে রাখো যাতে কেটে না যায়।"""

            user_p=f"""Context (আইনের হুবহু অংশ):
{context[:7000]}

প্রশ্ন: {q}

সুনির্দিষ্ট উত্তর দাও (প্রথম লাইনে সরাসরি উত্তর, তারপর ব্যাখ্যা):"""

            comp=groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"system","content":system},{"role":"user","content":user_p}],
                temperature=0.05,
                max_tokens=600,
            )
            final=comp.choices[0].message.content.strip()
            CACHE[key]=(final,[])
            return ChatResponse(answer=final, references=[], cached=False)
        except Exception as e:
            print(e)
            ans=relevant[0]["text"][:1200]
            CACHE[key]=(ans,[]); return ChatResponse(answer=ans, references=[], cached=False)
    else:
        ans=relevant[0]["text"][:1200]
        CACHE[key]=(ans,[]); return ChatResponse(answer=ans, references=[], cached=False)
