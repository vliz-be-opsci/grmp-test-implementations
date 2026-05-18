FROM python:3.11-slim

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git unzip ca-certificates nodejs npm \
    && rm -rf /var/lib/apt/lists/*

ENV BUN_INSTALL=/root/.bun
ENV PATH="/root/.bun/bin:${PATH}"

RUN curl -fsSL https://bun.sh/install | bash

COPY package.json /app/package.json
RUN cd /app && npm install --omit=dev

RUN mkdir -p /reports

COPY src /app/src

WORKDIR /app

RUN chmod +x /app/src/wrx_test.py /app/src/wrx_fetch.mjs

CMD ["python", "/app/src/wrx_test.py"]
