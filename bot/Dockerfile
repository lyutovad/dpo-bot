FROM python:3.11.4-slim-buster

# ENV PYTHONDONTWRITEBYTECODE=1
# ENV PYTHONUNBUFFERED=1

ARG DB_USER
ARG DB_PASSWORD
ARG DB_HOST
ARG DB_PORT
ARG DB_NAME
ARG TG_BOT_TOKEN 
ARG OLLAMA_HOST
ARG OLLAMA_MODEL

WORKDIR /app

RUN apt-get update && apt upgrade -y && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    curl\
    g++ && export LANGCHAIN_TRACING_V2=true && export LANGCHAIN_API_KEY=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

COPY ./requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["python", "-u", "main_bot.py"]