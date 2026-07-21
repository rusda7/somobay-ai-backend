
from fastapi import FastAPI, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import hashlib
from utils.pdf_loader import extract_bangla_pdf
from utils.rag import get_answer_from_docs
app = FastAPI(title="Somobay AI Backend")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
cache = {}
class ChatReq(BaseModel):
    question: str
    user_id: str
@app.get("/")
def root():
    return {"status": "Somobay AI Backend Running"}
@app.post("/api/chat")
def chat(req: ChatReq):
    q = req.question.strip()
    q_hash = hashlib.md5(q.lower().encode()).hexdigest()
    if q_hash in cache:
        data = cache[q_hash].copy()
        data['cached'] = True
        return data
    answer, refs = get_answer_from_docs(q)
    result = {"answer": answer, "references": refs, "cached": False}
    cache[q_hash] = result
    return result
@app.post("/api/upload-law")
async def upload_law(file: UploadFile):
    path = f"/tmp/{file.filename}"
    with open(path, "wb") as f:
        f.write(await file.read())
    text = extract_bangla_pdf(path)
    return {"message": "Indexed", "chars": len(text)}
