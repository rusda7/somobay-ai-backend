FROM python:3.11-slim

WORKDIR /app

# llama-cpp-python বিল্ড করার জন্য cmake, g++, git লাগবে
RUN apt-get update && apt-get install -y build-essential cmake git unzip

COPY . .

RUN unzip chroma_db.zip && rm chroma_db.zip

# CMAKE_ARGS দিলে CPU-only বিল্ড হবে, GPU ছাড়া
ENV CMAKE_ARGS="-DLLAMA_BLAS=ON -DLLAMA_BLAS_VENDOR=OpenBLAS"
ENV FORCE_CMAKE=1
RUN apt-get update && apt-get install -y build-essential cmake git unzip

EXPOSE 10000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "10000"]