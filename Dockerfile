FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y git git-lfs unzip && git lfs install

COPY . .

RUN git lfs pull

RUN unzip chroma_db.zip && rm chroma_db.zip

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 10000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "10000"]