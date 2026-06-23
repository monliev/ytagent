FROM python:3.11-slim

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements from root context
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the app source code
COPY app/ ./app/
COPY scripts/ ./scripts/

# Run Alembic migrations then start Uvicorn
CMD ["sh", "-c", "cd /app && alembic -c app/alembic.ini upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
