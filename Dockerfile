# Use a small Python base image
FROM python:3.13-slim

# Avoid .pyc and use unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Workdir inside the container
WORKDIR /app

# Install build tools for any native deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Expose FastAPI port
EXPOSE 8000

# CTA_TRAIN_API_KEY will be provided at runtime
ENV CTA_DB_PATH=/app/cta_trains.db

# Start both the extractor and the FastAPI server
ENTRYPOINT ["/app/entrypoint.sh"]
