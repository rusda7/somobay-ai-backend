
# সমবায় আইন AI - Deploy Guide

## ধাপ ১: GitHub
- github.com এ নতুন repo: somobay-ai
- এই zip extract করে frontend ও backend push করুন

## ধাপ ২: Backend - Render.com
1. render.com > New Web Service > Connect Repo
2. Root Directory: backend
3. Build: pip install -r requirements.txt
4. Start: uvicorn main:app --host 0.0.0.0 --port 10000
5. ENV: OPENAI_API_KEY বা GROQ_API_KEY
6. Deploy - URL কপি

## ধাপ ৩: Frontend - Vercel.com
1. vercel.com > New Project > Same Repo
2. Root Directory: frontend
3. ENV: NEXT_PUBLIC_API_URL = Render URL
4. Deploy

## ধাপ ৪: বাংলা PDF সমস্যা সমাধান
Render এ Dockerfile ব্যবহার করুন, তাতে tesseract-ocr-ben ইনস্টল করা আছে।

Done!
