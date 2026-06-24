FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /

RUN pip install --no-cache-dir watchdog httpx

# Copy src to the correct service folder path to preserve relative import paths
COPY src/ /services/filewatcher/src/

ENV PYTHONPATH=/

CMD ["python", "-m", "services.filewatcher.src.main"]
