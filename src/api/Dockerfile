FROM python:3.8-slim

WORKDIR /app

# Copy requirements
COPY src/requirements/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy API code
COPY src/api /app/api
COPY src/storage /app/storage

# Set environment variables
ENV PYTHONPATH=/app
ENV FLASK_APP=api/app.py
ENV FLASK_ENV=development

# Expose port
EXPOSE 8001

# Run the API
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=8001"]
