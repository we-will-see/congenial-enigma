FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        libglib2.0-0 \
        libgl1 \
        tesseract-ocr \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts
COPY deploy/entrypoint.sh /usr/local/bin/enigma-entrypoint

RUN groupadd --system enigma \
    && useradd --system --gid enigma --home-dir /app enigma \
    && mkdir -p /app/data/documents \
    && chown -R enigma:enigma /app/data \
    && chmod 0755 /usr/local/bin/enigma-entrypoint

USER enigma

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/enigma-entrypoint"]
