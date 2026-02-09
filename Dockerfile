FROM python:3.11-slim

RUN pip install --no-cache-dir junitparser

RUN mkdir -p /reports

COPY src/input_echo_test.py /app/test_worker.py

WORKDIR /app

RUN chmod +x test_worker.py

CMD ["python", "test_worker.py"]
