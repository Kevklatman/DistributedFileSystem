FROM python:3.8-slim

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/storage /app/storage
COPY src/api /app/api

# Set environment variables
ENV PYTHONPATH=/app

# Set working directory to storage node code
WORKDIR /app/storage

# Run storage node
CMD ["python", "node.py"]
