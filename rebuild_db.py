# rebuild_db.py
import os, shutil, chromadb
from sentence_transformers import SentenceTransformer
import PyPDF2

# পুরান DB ডিলিট
if os.path.exists("chroma_db"):
    shutil.rmtree("chroma_db")
    print("পুরান DB ডিলিট করা হলো")

# বাংলা বোঝে এমন মডেল (200MB ডাউনলোড হবে প্রথমবার)
print("মডেল ডাউনলোড হচ্ছে... 2 মিনিট লাগবে")
model = SentenceTransformer('l3cube-pune/indic-sentence-bert-nli')
print("মডেল রেডি!")

client = chromadb.PersistentClient(path="chroma_db")
collection = client.create_collection(name="somobay_law", metadata={"hnsw:space": "cosine"})

pdf_folder = "pdfs"
chunk_id = 0
for pdf_file in os.listdir(pdf_folder):
    if not pdf_file.lower().endswith(".pdf"):
        continue
    print(f"পড়ছি: {pdf_file}")
    reader = PyPDF2.PdfReader(os.path.join(pdf_folder, pdf_file))
    full_text = ""
    for page in reader.pages:
        txt = page.extract_text()
        if txt:
            full_text += txt + "\n"

    # 1500 character chunk, 300 overlap - আইনের ধারা কাটবে না
    for i in range(0, len(full_text), 1200):
        chunk = full_text[i:i+1500]
        if len(chunk.strip()) < 100:
            continue
        emb = model.encode(chunk).tolist()
        collection.add(
            ids=[str(chunk_id)],
            documents=[chunk],
            embeddings=[emb],
            metadatas=[{"source": pdf_file}]
        )
        chunk_id += 1

print(f"\n✅ নতুন DB রেডি! মোট {collection.count()} টি টুকরা")
print("এখন GitHub Desktop দিয়ে Push করেন")