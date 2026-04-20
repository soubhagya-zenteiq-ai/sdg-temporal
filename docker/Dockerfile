# Base image
FROM python:3.11-slim

# Prevent python from buffering logs
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# System dependencies (important for llama.cpp + psycopg2)
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy full project
COPY . .

# Create models directory (if not present)
RUN mkdir -p /app/models

# Default command → run worker
CMD ["python", "-m", "app.workers.worker"]