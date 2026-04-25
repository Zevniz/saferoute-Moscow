FROM python:3.10-slim

# Установка системных зависимостей для работы с геоданными
RUN apt-get update && apt-get install -y \
    gdal-bin libgdal-dev spatialite-bin libsqlite3-mod-spatialite \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
