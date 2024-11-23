FROM python:3.9-slim

WORKDIR /app

# Copy requirements
COPY src/requirements/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src /app/src

# Set environment variables
ENV PYTHONPATH=/app/src
ENV FLASK_APP=api/app.py
ENV FLASK_ENV=production

# Create storage directory
RUN mkdir -p /app/storage/buckets

# Expose port
EXPOSE 8080

# Run the API
CMD ["python", "-m", "api.app"]