FROM python:3.8-slim

WORKDIR /app

# Copy requirements
COPY src/requirements/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src /app/src

# Clean up Python bytecode cache files
RUN find /app -type d -name "__pycache__" -exec rm -r {} +

# Set environment variables
ENV PYTHONPATH=/app
ENV FLASK_APP=src/api/app.py

# Create storage directory
RUN mkdir -p /app/storage/buckets

# Expose port
EXPOSE 8080

# Run the application
CMD ["python", "-m", "src.api.app"]