FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY src ./src

# Create data and cache directories
RUN mkdir -p /data /data/cache && \
    chmod 750 /data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
ENV STORAGE_DATA_DIR=/data
ENV CACHE_DIR=/data/cache
ENV NODE_ID=
ENV PORT=8080
ENV METRICS_PORT=9091
ENV HOST=0.0.0.0

# Create volume for persistent storage
VOLUME ["/data"]

# Expose ports
EXPOSE 8080
EXPOSE 9091

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the storage node
CMD ["python", "-m", "src.storage.core.node"]
