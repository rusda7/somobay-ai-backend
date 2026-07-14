import os
import chromadb
from llama_cpp import Llama
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Somobay AI Backend")

# Render এর পোর্ট নিবে, লোকালে 10000
PORT = int(os.environ.get("PORT", 10000))

# 1. ChromaDB Client - এরর হ্যান্ডেল সহ
print("Loading ChromaDB...")
try:
    chroma_client = chromadb.PersistentClient(path="./chroma_db")
    collection = chroma_client.get_collection("somobay_law")
    print("ChromaDB collection 'somobay_law' loaded successfully")
except Exception as e:
    print(f"ChromaDB Error: {e}")
    print("Creating new empty collection 'somobay_law'...")
    collection = chroma_client.create_collection("somobay_law")

# 2. LLM Model - ফাইল চেক সহ
MODEL_PATH = "./qwen2.5-1.5b-instruct-q4_k_m.gguf"
print(f"Checking model file: {MODEL_PATH}")

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"Model file not found: {MODEL_PATH}. Check if GIT_LFS_ENABLED=true")

print("Loading LLM model... This takes time")
llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=2048,
    n_threads=2, # Free plan এ 2 CPU
    n_gpu_layers=0 # CPU only
)
print("LLM loaded successfully")

class Query(BaseModel):
    question: str

@app.get("/")
def read_root():
    return {"status": "Somobay AI is running"}

@app.post("/ask")
def ask_question(query: Query):
    # RAG: ChromaDB থেকে রিলেভেন্ট ডকুমেন্ট নিবে
    results = collection.query(
        query_texts=[query.question],
        n_results=2
    )
    
    context = "\n".join(results['documents'][0]) if results['documents'] else "No context found."
    
    prompt = f"""Context: {context}
    
Question: {query.question}
Answer in Bengali:"""
    
    output = llm(prompt, max_tokens=512, stop=["Question:", "\n"])
    return {"answer": output['choices'][0]['text'].strip()}

# Render এর জন্য এইটা জরুরি
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)