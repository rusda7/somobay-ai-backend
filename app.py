import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
import httpx
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Somobay AI", version="1.0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_KEY = os.environ.get("GROQ_API_KEY")
print(f"GROQ_API_KEY Found: {bool(GROQ_KEY)}")

try:
    if GROQ_KEY:
        http_client = httpx.Client()
        client = Groq(api_key=GROQ_KEY, http_client=http_client)
        print("Groq client initialized successfully")
    else:
        client = None
        print("Groq client NOT initialized - Key missing")
except Exception as e:
    print(f"Groq client init failed: {e}")
    client = None

class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    answer: str

SOMOBAY_LAW_CONTEXT = """
ধারা ১৮: সমবায় সমিতির সদস্য হওয়ার যোগ্যতা। ১৮ বছর বা তার বেশি বয়সী, সুস্থ মস্তিষ্কের যেকোনো বাংলাদেশী নাগরিক সদস্য হতে পারবে।
ধারা ২২: সমিতির ব্যবস্থাপনা কমিটি। ৬ জন থেকে ১২ জন সদস্য নিয়ে ব্যবস্থাপনা কমিটি গঠিত হবে। কমিটির মেয়াদ ৩ বছর।
ধারা ৩৫: বার্ষিক সাধারণ সভা। প্রতি সমবায় বর্ষ শেষ হওয়ার ৬ মাসের মধ্যে অন্তত একবার বার্ষিক সাধারণ সভা করতে হবে।
"""

@app.get("/")
def read_root():
    return {
        "status": "Somobay AI is Live on Free Plan!",
        "groq_status": "OK" if client else "GROQ_API_KEY missing or invalid"
    }

@app.post("/ask", response_model=QueryResponse)
def ask_question(request: QueryRequest):
    if not client:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY সেট করা নাই বা ভুল। Render Environment চেক করেন।")
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="প্রশ্ন খালি রাখা যাবে না।")
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": f"তুমি একজন বাংলাদেশী সমবায় আইন বিশেষজ্ঞ। নিচের প্রসঙ্গ ব্যবহার করে উত্তর দাও।\n\nপ্রসঙ্গ:\n{SOMOBAY_LAW_CONTEXT}"},
                {"role": "user", "content": request.question}
            ],
            model="llama-3.1-8b-instant", # এইটা নতুন মডেল
            temperature=0.2,
            max_tokens=1024,
        )
        answer = chat_completion.choices[0].message.content
        return QueryResponse(answer=answer)
    except Exception as e:
        print(f"Groq API Error: {e}")
        raise HTTPException(status_code=500, detail=f"AI সার্ভারে সমস্যা: {str(e)}")

@app.get("/health")
def health_check():
    return {"status": "ok"}