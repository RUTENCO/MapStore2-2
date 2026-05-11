FROM python:3.11.9-slim

ENV PYTHONUNBUFFERED=1 \
    MODEL_DATA_ROOT=/data/datalake \
    CRON_SCHEDULE="0 3 15 * *"

RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    g++ \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY start.sh /start.sh

RUN sed -i 's/\r$//' /start.sh \
    && chmod +x /start.sh \
    && mkdir -p /data/datalake/logs \
    && mkdir -p /data/datalake/Geodata/raster_results \
    && mkdir -p /data/datalake/img_results \
    && mkdir -p /data/datalake/models

CMD ["/start.sh"]
