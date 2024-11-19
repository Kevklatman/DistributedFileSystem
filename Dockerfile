FROM python:3.8-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/api ./api

# Copy environment file
COPY .env.example .env

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=8000
ENV HOST=0.0.0.0

# Create data directory
RUN mkdir -p /app/data

# Expose port
EXPOSE 8000

# Run the storage node
CMD ["python", "-u", "/app/api/storage/node.py"]
