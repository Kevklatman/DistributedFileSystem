FROM python:3.8-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/api ./api
COPY .env.example .env

# Set environment variables
ENV PYTHONPATH=/app
ENV FLASK_APP=api/app.py
ENV FLASK_ENV=production

# Expose port
EXPOSE 5555

# Run the application
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0"]
