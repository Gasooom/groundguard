FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV GROUNDGUARD_DATABASE_PATH=/app/data/groundguard.db

RUN mkdir -p /app/data

COPY pyproject.toml README.md ./

RUN pip install --no-cache-dir \
    "fastapi>=0.115,<1" \
    "uvicorn[standard]>=0.34,<1"

COPY groundguard ./groundguard

EXPOSE 8000

CMD ["uvicorn", "groundguard.api.app:app", "--host", "0.0.0.0", "--port", "8000"]