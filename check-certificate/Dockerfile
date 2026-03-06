FROM python:3.11-slim

COPY requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir -r /tmp/requirements.txt

RUN mkdir -p /reports

COPY src/check_certificate.py /app/check_certificate.py

WORKDIR /app

RUN chmod +x check_certificate.py

CMD ["python", "check_certificate.py"]
