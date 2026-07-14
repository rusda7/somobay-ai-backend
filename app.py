import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
import httpx
from dotenv import load_dotenv

# ChromaDB এর জন্য নতুন ইম্পোর্ট
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

load_dotenv()

app = FastAPI(title="Somobay AI", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ১. Groq ক্লায়েন্ট সেটআপ ---
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

# --- ২. ChromaDB সেটআপ ---
# Render ফ্রি প্ল্যানে CPU দিয়ে embedding চালাবো
embedding_function = HuggingFaceEmbeddings(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    model_kwargs={'device': 'cpu'}
)

try:
    # persist_directory="chroma_db" মানে আপনার আপলোড করা ফোল্ডার
    db = Chroma(persist_directory="chroma_db", embedding_function=embedding_function)
    print("ChromaDB loaded successfully")
except Exception as e:
    print(f"ChromaDB load failed: {e}")
    db = None

class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    answer: str
    sources: list[str] = [] # কোন ধারা থেকে উত্তর আসলো সেটাও দেখাবো

@app.get("/")
def read_root():
    return {
        "status": "Somobay AI is Live with RAG!",
        "groq_status": "OK" if client else "GROQ_API_KEY missing",
        "db_status": "OK" if db else "ChromaDB missing"
    }

@app.post("/ask", response_model=QueryResponse)
def ask_question(request: QueryRequest):
    if not client:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY সেট করা নাই")
    if not db:
        raise HTTPException(status_code=500, detail="ChromaDB লোড হয় নাই")
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="প্রশ্ন খালি রাখা যাবে না।")
    
    try:
        # --- ৩. RAG এর মূল কাজ: ChromaDB থেকে রিলেভেন্ট ডকুমেন্ট খোঁজা ---
        # ইউজারের প্রশ্নের সাথে মিলে এমন 4টা ডকুমেন্ট বের করো
        docs = db.similarity_search(request.question, k=4)
        
        # ডকুমেন্টগুলা একসাথে করে Context বানানো
        context_text = "\n\n---\n\n".join([doc.page_content for doc in docs])
        sources = [doc.metadata.get('source', 'Unknown') for doc in docs] # সোর্সের নাম

        # --- ৪. Groq কে Context সহ প্রশ্ন করা ---
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system", 
                    "content": f"""তুমি একজন বাংলাদেশী সমবায় আইন বিশেষজ্ঞ। তোমার নাম Somobay AI। 
                    তোমাকে ইউজারের প্রশ্নের উত্তর দিতে হবে নিচের 'প্রসঙ্গ' ব্যবহার করে। 
                    উত্তর সংক্ষিপ্ত, সহজ বাংলায় এবং বন্ধুত্বপূর্ণ ভাবে দিবে। 
                    যদি প্রসঙ্গে উত্তর না থাকে, তাহলে বলবে 'দুঃখিত, আমার ডাটাবেসে এই তথ্যটি এখন নেই।'

                    প্রসঙ্গ:
                    {context_text}
                    """
                },
                {"role": "user", "content": request.question}
            ],
            model="llama-3.1-8b-instant",
            temperature=0.1, # কম রাখলে ডাটার বাইরে যাবে না
            max_tokens=1024,
        )
        answer = chat_completion.choices[0].message.content
        return QueryResponse(answer=answer, sources=list(set(sources))) # ডুপ্লিকেট সোর্স বাদ

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=f"AI সার্ভারে সমস্যা: {str(e)}")

@app.get("/health")
def health_check():
    return {"status": "ok"}