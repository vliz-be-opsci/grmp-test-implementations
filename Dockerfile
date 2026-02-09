FROM python:3.11-slim

COPY requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir -r /tmp/requirements.txt

RUN mkdir -p /reports

COPY src/input_echo_test.py /app/test_worker.py

WORKDIR /app

RUN chmod +x test_worker.py

CMD ["python", "test_worker.py"]
