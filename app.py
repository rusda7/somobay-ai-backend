import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv

#.env ফাইল থেকে Environment Variable লোড করার জন্য
load_dotenv()

# FastAPI অ্যাপ চালু
app = FastAPI(
    title="Somobay AI",
    description="বাংলাদেশ সমবায় আইন বিষয়ক AI সহকারী",
    version="1.0.0"
)

# CORS অ্যাড করা যাতে যেকোনো জায়গা থেকে API কল করা যায়
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Groq ক্লায়েন্ট চালু করা। Render এর Environment থেকে GROQ_API_KEY নিবে
try:
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except Exception as e:
    print(f"Groq client init failed: {e}")
    client = None

# রিকোয়েস্ট আর রেসপন্সের মডেল
class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    answer: str

# আপাতত সমবায় আইনের কিছু ডাটা এখানেই রাখলাম। পরে ChromaDB অ্যাড করব।
SOMOBAY_LAW_CONTEXT = """
বাংলাদেশ সমবায় সমিতি আইন, ২০০১ ও সমবায় সমিতি বিধিমালা, ২০০৪ অনুযায়ী:

ধারা ১৮: সমবায় সমিতির সদস্য হওয়ার যোগ্যতা। ১৮ বছর বা তার বেশি বয়সী, সুস্থ মস্তিষ্কের যেকোনো বাংলাদেশী নাগরিক সদস্য হতে পারবে। দেউলিয়া বা নৈতিক স্খলনের দায়ে দণ্ডিত ব্যক্তি সদস্য হতে পারবে না।

ধারা ২২: সমিতির ব্যবস্থাপনা কমিটি। ৬ জন থেকে ১২ জন সদস্য নিয়ে ব্যবস্থাপনা কমিটি গঠিত হবে। কমিটির মেয়াদ ৩ বছর।

ধারা ৩৫: বার্ষিক সাধারণ সভা (AGM)। প্রতি সমবায় বর্ষ শেষ হওয়ার ৬ মাসের মধ্যে অন্তত একবার বার্ষিক সাধারণ সভা করতে হবে।

ধারা ৪৮: সমিতির তহবিল। সদস্যদের শেয়ার, সঞ্চয়, আমানত, ঋণ এবং অনুদান নিয়ে সমিতির তহবিল গঠিত হয়।

বিধি ২০: ঋণ প্রদান। কোনো সদস্যকে তার জমাকৃত শেয়ার ও সঞ্চয়ের ১০ গুণের বেশি ঋণ দেওয়া যাবে না।
"""

@app.get("/")
def read_root():
    """সার্ভার চালু আছে কিনা চেক করার জন্য"""
    return {
        "status": "Somobay AI is Live on Free Plan!",
        "groq_status": "OK" if client else "GROQ_API_KEY missing"
    }

@app.post("/ask", response_model=QueryResponse)
def ask_question(request: QueryRequest):
    """
    ইউজারের প্রশ্নের উত্তর দেয়। Groq API ইউজ করে।
    """
    if not client:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY সেট করা নাই বা ভুল। Render Environment চেক করেন।")

    if not request.question.strip():
        raise HTTPException(status_code=400, detail="প্রশ্ন খালি রাখা যাবে না।")

    try:
        # Groq API কে কল করা
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": f"""তুমি একজন বাংলাদেশী সমবায় আইন বিশেষজ্ঞ। তোমার নাম Somobay AI। 
                    তোমাকে ইউজারের প্রশ্নের উত্তর দিতে হবে নিচের 'প্রসঙ্গ' ব্যবহার করে। 
                    উত্তর সংক্ষিপ্ত, সহজ বাংলায় এবং বন্ধুত্বপূর্ণ ভাবে দিবে। 
                    যদি প্রসঙ্গে উত্তর না থাকে, তাহলে বলবে 'দুঃখিত, আমার কাছে এই তথ্যটি এখন নেই।' বানিয়ে কোনো উত্তর দিবে না।

                    প্রসঙ্গ:
                    {SOMOBAY_LAW_CONTEXT}
                    """
                },
                {
                    "role": "user",
                    "content": request.question,
                }
            ],
            model="llama3-8b-8192", # Groq এর ফ্রি এবং ফাস্ট মডেল
            temperature=0.2, # কম রাখলে বানিয়ে বলার চান্স কম
            max_tokens=1024,
        )
        answer = chat_completion.choices[0].message.content
        return QueryResponse(answer=answer)

    except Exception as e:
        print(f"Groq API Error: {e}")
        raise HTTPException(status_code=500, detail=f"AI সার্ভারে সমস্যা হয়েছে: {str(e)}")

@app.get("/health")
def health_check():
    """Render এর Health Check এর জন্য"""
    return {"status": "ok"}