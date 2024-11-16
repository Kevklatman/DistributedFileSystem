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
ENV PYTHONPATH=/app/api
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# Expose port
EXPOSE 5000

# Run the application with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--threads", "2", "--worker-class", "gthread", "--log-level", "debug", "--access-logfile", "-", "--error-logfile", "-", "--chdir", "/app/api", "app:app"]
