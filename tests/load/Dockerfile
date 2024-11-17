FROM locustio/locust

WORKDIR /mnt/locust
COPY locustfile.py .

EXPOSE 8089

CMD ["--host", "${TARGET_HOST}", "--web-host", "0.0.0.0"]
