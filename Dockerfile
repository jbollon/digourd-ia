FROM python:3.11-slim

# Dipendenza di sistema per faiss-cpu
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dipendenze Python (layer cacheable)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Codice applicazione
COPY app/ ./app/

# Indice FAISS + metadata + modello di embedding (cache fastembed)
COPY storage/ ./storage/

# Cloud Run inietta la variabile PORT; default 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips='*'"]
