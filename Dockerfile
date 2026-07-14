FROM python:3.11-slim

WORKDIR /app

# Build tools + git-lfs লাগবে
RUN apt-get update && apt-get install -y build-essential cmake git git-lfs unzip curl && git lfs install

COPY . .

# LFS ফাইল টানবে আর unzip করবে। এরর হলেও বিল্ড থামবে না
RUN git lfs pull || true
RUN unzip -o chroma_db.zip || echo "chroma_db.zip not found, skipping"

ENV CMAKE_ARGS="-DLLAMA_BLAS=ON -DLLAMA_BLAS_VENDOR=OpenBLAS"
ENV FORCE_CMAKE=1
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 10000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "10000"]