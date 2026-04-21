FROM python:3.13-slim

WORKDIR /app

# System dependencies for psycopg2
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Use headless opencv (no OpenGL/display needed on server)
COPY requirements.txt .
RUN sed 's/opencv-python==/opencv-python-headless==/g' requirements.txt > requirements_docker.txt \
    && pip install --no-cache-dir -r requirements_docker.txt \
    && rm requirements_docker.txt

COPY app/ ./app/

EXPOSE 8000

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
