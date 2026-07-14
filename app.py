import os
from fastapi import FastAPI
from contextlib import asynccontextmanager

# গ্লোবাল ভ্যারিয়েবল - খালি রাখেন
llm = None
collection = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global llm, collection
    print("🚀 App starting...")
    
    # ChromaDB লোড - ক্র্যাশ করলেও অ্যাপ মরবে না
    try:
        import chromadb
        chroma_client = chromadb.PersistentClient(path="./chroma_db")
        collection = chroma_client.get_or_create_collection("somobay_law")
        print(f"✅ ChromaDB OK. Docs: {collection.count()}")
    except Exception as e:
        print(f"⚠️ ChromaDB failed: {e}")
        collection = None
    
    # Llama লোড
    try:
        from llama_cpp import Llama
        model_path = "./qwen2.5-1.5b-instruct-q4_k_m.gguf"
        if os.path.exists(model_path):
            llm = Llama(model_path=model_path, n_ctx=2048, n_gpu_layers=0, verbose=False)
            print("✅ Llama model loaded")
        else:
            print(f"⚠️ Model file not found: {model_path}")
    except Exception as e:
        print(f"⚠️ Llama failed: {e}")
        llm = None

    print("🚀 App is ready")
    yield
    print("App shutting down")

app = FastAPI(lifespan=lifespan)

@app.get("/")
def read_root():
    return {
        "status": "Live",
        "chroma_status": "OK" if collection else "Failed",
        "llm_status": "OK" if llm else "Failed"
    }

@app.get("/health")
def health():
    return {"status": "ok"}