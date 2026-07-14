import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    answer: str

SOMOBAY_LAW_CONTEXT = """
ধারা ১৮: সমবায় সমিতির সদস্য হওয়ার যোগ্যতা। ১৮ বছর বয়সী, সুস্থ মস্তিষ্কের যেকোনো বাংলাদেশী নাগরিক সদস্য হতে পারবে।
ধারা ২২: সমিতির ব্যবস্থাপনা কমিটি। ৬ থেকে ১২ জন সদস্য নিয়ে কমিটি গঠিত হবে। কমিটির মেয়াদ ৩ বছর।
"""

@app.get("/")
def read_root():
    return {"status": "Somobay AI is Live on Free Plan!"}

@app.post("/ask", response_model=QueryResponse)
def ask_question(request: QueryRequest):
    if not os.environ.get("GROQ_API_KEY"):
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not set")
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": f"তুমি একজন বাংলাদেশী সমবায় আইন বিশেষজ্ঞ। নিচের প্রসঙ্গ ব্যবহার করে ইউজারের প্রশ্নের উত্তর দাও।\n\nপ্রসঙ্গ:\n{SOMOBAY_LAW_CONTEXT}"},
                {"role": "user", "content": request.question}
            ],
            model="llama3-8b-8192",
        )
        answer = chat_completion.choices[0].message.content
        return QueryResponse(answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))