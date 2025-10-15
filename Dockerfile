    FROM python:3.11-slim
    WORKDIR /my-app
    ENV PYTHONPATH="/my-app"
    RUN apt-get update && apt-get install -y \
        ffmpeg \
        libpq-dev \
        gcc \
        curl \
        && rm -rf /var/lib/apt/lists/*
    COPY requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt
    COPY . .
    RUN sed -i 's/\r$//' prestart.sh
    RUN chmod +x prestart.sh
    EXPOSE 8000
    CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]