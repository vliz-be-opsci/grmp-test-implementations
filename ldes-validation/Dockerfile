FROM python:3.11-slim

COPY requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir -r /tmp/requirements.txt

RUN mkdir -p /reports

COPY src/ldes_validation.py /app/ldes_validation.py
COPY shapes/ /app/shapes/

WORKDIR /app

RUN chmod +x ldes_validation.py

CMD ["python", "ldes_validation.py"]
