FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt requirements-deploy.txt ./
RUN pip install -r requirements-deploy.txt

COPY . .

# Render injects $PORT; default 8000 elsewhere
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
