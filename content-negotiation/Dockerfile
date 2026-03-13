FROM python:3.11-slim

COPY requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir -r /tmp/requirements.txt

RUN mkdir -p /reports

COPY src/content_negotiation.py /app/content_negotiation.py

WORKDIR /app

RUN chmod +x content_negotiation.py

CMD ["python", "content_negotiation.py"]
