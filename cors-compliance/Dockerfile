FROM python:3.11-slim

COPY requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir -r /tmp/requirements.txt

RUN mkdir -p /reports

COPY src/cors_compliance.py /app/cors_compliance.py

WORKDIR /app

RUN chmod +x cors_compliance.py

CMD ["python", "cors_compliance.py"]
