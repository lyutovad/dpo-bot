FROM python:3.11.4-slim-buster

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
EXPOSE 8100

CMD ["python", "-u", "main_app.py"]