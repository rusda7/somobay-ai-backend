FROM python:3.11-slim

WORKDIR /app

# ১. requirements.txt কপি করো /app ফোল্ডারে
COPY requirements.txt .

# ২. প্যাকেজ ইনস্টল করো
RUN pip install --no-cache-dir -r requirements.txt

# ৩. বাকি সব ফাইল কপি করো
COPY . .

# ৪. পোর্ট ওপেন করো
EXPOSE 10000

# ৫. অ্যাপ চালাও
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "10000"]