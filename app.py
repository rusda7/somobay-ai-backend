from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import chromadb, os
from llama_cpp import Llama

app = FastAPI(title="সমবায় AI সহায়ক")
security = HTTPBearer()

# CORS - HuggingFace Static থেকে কল আসবে
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ভেক্টর DB লোড
chroma_client = chromadb.PersistentClient(path="./chroma_db")
try:
    collection = chroma_client.get_collection("somobay_law")
except:
    collection = chroma_client.create_collection("somobay_law")
    # ডাটা আবার ইনজেস্ট করতে হবে, কিন্তু অ্যাপ ক্র্যাশ করবে না

# LLM লোড - CPU তে চলবে
llm = Llama(
    model_path="./qwen2.5-1.5b-instruct-q4_k_m.gguf",  # এই লাইনটা চেঞ্জ
    n_ctx=4096,
    n_threads=4,
    verbose=False
)

@app.get("/")
def health_check():
    return {"status": "জীবিত আছি"} # UptimeRobot এর জন্য

@app.post("/login")
def login(data: dict):
    # আপাতত ডেমো। পরে DB বসাবেন
    if data.get("email") and data.get("password"):
        return {"token": "demo_token_123", "plan": "free", "limit": 20}
    raise HTTPException(401, "ভুল ইমেইল বা পাসওয়ার্ড")

@app.post("/ask")
def ask_question(data: dict, token: HTTPAuthorizationCredentials = Depends(security)):
    question = data.get("question", "")
    if not question:
        raise HTTPException(400, "প্রশ্ন লিখুন")

    # ধাপ ১: আইনে সার্চ
    results = collection.query(query_texts=[question], n_results=3)

    if not results['documents'][0]:
        return {
            "answer": "দুঃখিত, সমবায় আইন ২০০১ বা বিধিমালা ২০০৪ এ এই বিষয়ে সরাসরি কিছু পাওয়া যায়নি। জেলা সমবায় অফিসে যোগাযোগ করুন।",
            "references": []
        }

    context = "\n\n".join(results['documents'][0])
    sources = results['metadatas'][0]

    # ধাপ ২: LLM কে দিয়ে উত্তর বানাও - মনগড়া নিষেধ
    prompt = f"""তুমি সমবায় আইন বিশেষজ্ঞ। নিচের আইন/বিধিমালা অংশগুলো পড়ে উত্তর দাও।
নিয়ম:
1. শুধু নিচের দেওয়া তথ্য থেকে উত্তর দেবে।
2. বাইরের জ্ঞান ব্যবহার করবে না।
3. উত্তর না পেলে বলবে 'আইনে পাওয়া যায়নি'।
4. সহজ বাংলায় বুঝিয়ে বলবে এবং ধারা নম্বর উল্লেখ করবে।

আইনের অংশ:
{context}

প্রশ্ন: {question}
উত্তর:"""

    output = llm(prompt, max_tokens=512, temperature=0.1, stop=["প্রশ্ন:"])
    answer = output['choices'][0]['text'].strip()

    # রেফারেন্স বানাও
    refs = []
    for s in sources:
        refs.append(f"{s.get('source', '')}, {s.get('section', '')}")

    return {"answer": answer, "references": list(set(refs))}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)