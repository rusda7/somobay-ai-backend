FROM python:3.11-slim

WORKDIR /app

# LFS আর unzip এর জন্য git আর unzip ইনস্টল করা লাগবে
RUN apt-get update && apt-get install -y git git-lfs unzip && git lfs install

# সব ফাইল কপি করেন
COPY . .

# LFS ফাইল টানেন
RUN git lfs pull

# chroma_db আনজিপ করেন
RUN unzip chroma_db.zip && rm chroma_db.zip

# Python প্যাকেজ ইনস্টল
RUN pip install --no-cache-dir -r requirements.txt

# পোর্ট খুলেন
EXPOSE 10000

# অ্যাপ চালান
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "10000"]