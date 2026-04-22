FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY pyproject.toml README.md app.py ./
COPY src ./src
COPY static ./static
COPY scripts ./scripts

RUN pip install -e . \
    && chmod +x scripts/start.sh \
    && mkdir -p data logs

EXPOSE 8000

CMD ["./scripts/start.sh"]
