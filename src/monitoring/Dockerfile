FROM python:3.8-slim

WORKDIR /app

# Copy requirements first
COPY src/monitoring/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy monitoring application files
COPY src/monitoring/app.py ./
COPY src/monitoring/templates ./templates/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

EXPOSE 5000

CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=5000"]
