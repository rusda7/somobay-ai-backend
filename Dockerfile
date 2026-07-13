FROM python:3.11-slim

WORKDIR /app

# unzip ইনস্টল লাগবে শুধু
RUN apt-get update && apt-get install -y unzip

# Render নিজেই LFS সহ সব ফাইল কপি করে দিবে
COPY . .

# chroma_db আনজিপ করেন
RUN unzip chroma_db.zip && rm chroma_db.zip

# Python প্যাকেজ ইনস্টল
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 10000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "10000"]