FROM locustio/locust

WORKDIR /mnt/locust

# Copy requirements first
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy locust file
COPY locustfile.py .

EXPOSE 8089

CMD ["--host", "${TARGET_HOST}", "--web-host", "0.0.0.0"]
