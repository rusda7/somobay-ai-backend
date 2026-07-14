# 1. Python 3.11 এর slim ভার্সন ইউজ করতেছি
FROM python:3.11-slim

# 2. কাজের ডিরেক্টরি সেট করা
WORKDIR /app

# 3. সিস্টেম প্যাকেজ ইনস্টল: build-essential, cmake, git, git-lfs, unzip
# llama-cpp-python কম্পাইল করতে cmake লাগবে
# LFS ফাইল টানতে git-lfs লাগবে
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    git-lfs \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && git lfs install

# 4. প্রথমে requirements.txt কপি করি। এতে ক্যাশ ভালো কাজ করে
COPY requirements.txt .

# 5. Python প্যাকেজ ইনস্টল
# CMAKE_ARGS দিলে llama-cpp-python CPU দিয়ে বিল্ড হবে
ENV CMAKE_ARGS="-DLLAMA_BLAS=ON -DLLAMA_BLAS_VENDOR=OpenBLAS"
ENV FORCE_CMAKE=1
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6. বাকি সব ফাইল কপি করা
COPY . .

# 7. Git LFS ফাইলগুলা টানা। এরর হলেও বিল্ড থামবে না
RUN git lfs pull || echo "Git LFS pull failed or no LFS files, continuing..."

# 8. chroma_db.zip থাকলে unzip করা। না থাকলেও এরর দিবে না
# -o = overwrite, -d ./ = current directory তে extract
RUN if [ -f "chroma_db.zip" ]; then \
        echo "Unzipping chroma_db.zip..."; \
        unzip -o chroma_db.zip -d ./; \
        echo "Unzip complete."; \
    else \
        echo "chroma_db.zip not found, skipping unzip."; \
    fi

# 9. Render এর জন্য পোর্ট এক্সপোজ করা
EXPOSE 10000

# 10. অ্যাপ চালু করার কমান্ড
# --host 0.0.0.0 না দিলে Render পোর্ট খুঁজে পাবে না
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "10000"]