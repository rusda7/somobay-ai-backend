from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "Somobay AI is Live now!"}

@app.get("/health")
def health():
    return {"status": "ok"}