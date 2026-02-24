FROM python:3.11-slim

COPY requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir -r /tmp/requirements.txt

RUN mkdir -p /reports

COPY src/resource_availability.py /app/resource_availability.py

WORKDIR /app

RUN chmod +x resource_availability.py

CMD ["python", "resource_availability.py"]
