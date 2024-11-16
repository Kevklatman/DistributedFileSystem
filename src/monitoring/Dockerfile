FROM python:3.8-slim

WORKDIR /app

# Install required packages
COPY src/monitoring/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/monitoring/app.py ./
COPY src/monitoring/templates ./templates/

# Create directory for Kubernetes config
RUN mkdir -p /root/.kube

ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

EXPOSE 5000

CMD ["python", "-m", "flask", "run", "--host=0.0.0.0"]
