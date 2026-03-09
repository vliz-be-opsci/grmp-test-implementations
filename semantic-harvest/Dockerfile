FROM python:3.11-slim

COPY requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir -r /tmp/requirements.txt

RUN mkdir -p /reports

COPY src/semantic_harvest.py /app/semantic_harvest.py

WORKDIR /app

RUN chmod +x semantic_harvest.py

CMD ["python", "semantic_harvest.py"]
