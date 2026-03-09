FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir -r /tmp/requirements.txt

RUN mkdir -p /reports

COPY src/shacl_validation.py /app/shacl_validation.py

WORKDIR /app

RUN chmod +x shacl_validation.py

CMD ["python", "shacl_validation.py"]
