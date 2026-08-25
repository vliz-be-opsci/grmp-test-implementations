FROM python:3.11-slim

COPY requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir -r /tmp/requirements.txt

RUN mkdir -p /reports /app

COPY src/ /app/

WORKDIR /app

RUN chmod +x rt_test.py

CMD ["python", "rt_test.py"]
