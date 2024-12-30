FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt upgrade -y && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    curl\
    g++
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt 

COPY  . .
CMD ["python", "-u", "ollama_test.py"]