FROM python:3.8-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY src/csi/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/csi /app/csi

# Set Python path
ENV FLASK_APP=/app

# Make entrypoint script executable
COPY src/csi/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
