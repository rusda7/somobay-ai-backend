import os
import chromadb
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from llama_cpp import Llama
from langchain_community.embeddings import HuggingFaceEmbeddings
from contextlib import asynccontextmanager

# ====== ১. গ্লোবাল ভ্যারিয়েবল ======
# অ্যাপ স্টার্ট হওয়ার সময় একবারই লোড হবে
llm = None
collection = None
embedding_model = None

# ====== ২. FastAPI Lifespan: স্টার্টআপে মডেল লোড ======
@asynccontextmanager
async def lifespan(app: FastAPI):
    # এই কোড অ্যাপ স্টার্ট হওয়ার সময় রান হবে
    global llm, collection, embedding_model
    
    print("🚀 Starting Somobay AI...")
    
    # 2.1 Embedding মডেল লোড
    print("Loading embedding model...")
    embedding_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    
    # 2.2 ChromaDB লোড - এরর হ্যান্ডেল করা আছে
    print("Loading ChromaDB...")
    try:
        chroma_client = chromadb.PersistentClient(path="./chroma_db")
        collection = chroma_client.get_collection("somobay_law")
        print(f"✅ ChromaDB loaded. Total docs: {collection.count()}")
    except Exception as e:
        print(f"⚠️ ChromaDB error: {e}")
        print("Creating new empty collection...")
        chroma_client = chromadb.PersistentClient(path="./chroma_db")
        collection = chroma_client.create_collection("somobay_law")
    
    # 2.3 Llama LLM লোড
    print("Loading Llama model... This may take 1-2 minutes.")
    model_path = "./qwen2.5-1.5b-instruct-q4_k_m.gguf"
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")
        
    llm = Llama(
        model_path=model_path,
        n_ctx=4096,
        n_gpu_layers=0, # Render এ GPU নাই
        verbose=False
    )
    print("✅ Llama model loaded successfully")
    print("🚀 App is ready to serve requests")
    
    yield
    
    # এই কোড অ্যাপ বন্ধ হওয়ার সময় রান হবে
    print("Shutting down...")


# ====== ৩. FastAPI App ======
app = FastAPI(title="Somobay AI Backend", lifespan=lifespan)

# ====== ৪. Request/Response মডেল ======
class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    answer: str
    sources: list = []

# ====== ৫. হেলথ চেক এন্ডপয়েন্ট ======
@app.get("/")
def read_root():
    return {
        "status": "Somobay AI is running",
        "chromadb_docs": collection.count() if collection else 0
    }

# ====== ৬. মেইন RAG এন্ডপয়েন্ট ======
@app.post("/ask", response_model=QueryResponse)
def ask_question(request: QueryRequest):
    if not all([llm, collection, embedding_model]):
        raise HTTPException(status_code=503, detail="Server is still loading. Please try again.")

    try:
        # 6.1 ইউজারের প্রশ্ন থেকে ভেক্টর বানানো
        question_embedding = embedding_model.embed_query(request.question)
        
        # 6.2 ChromaDB থেকে সিমিলার ডকুমেন্ট খোঁজা
        results = collection.query(
            query_embeddings=[question_embedding],
            n_results=3
        )
        
        context_docs = results['documents'][0]
        sources = results['metadatas'][0] if results['metadatas'] else []
        
        # 6.3 Llama এর জন্য প্রম্পট বানানো
        context = "\n\n".join(context_docs)
        prompt = f"""তুমি একজন বাংলাদেশী আইন সহকারী। নিচের প্রসঙ্গ ব্যবহার করে ইউজারের প্রশ্নের উত্তর দাও। প্রসঙ্গে না থাকলে বলো 'আমার কাছে এই তথ্য নেই'।

প্রসঙ্গ:
{context}

প্রশ্ন: {request.question}

উত্তর:"""

        # 6.4 Llama দিয়ে উত্তর জেনারেট
        output = llm(
            prompt,
            max_tokens=512,
            stop=["প্রশ্ন:", "\n\n"],
            echo=False
        )
        answer = output['choices'][0]['text'].strip()
        
        return QueryResponse(answer=answer, sources=sources)

    except Exception as e:
        print(f"Error in /ask: {e}")
        raise HTTPException(status_code=500, detail=str(e))