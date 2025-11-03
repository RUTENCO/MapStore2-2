# Dockerfile para el Procesador de Lluvia IDEAM
FROM python:3.12-slim

# Metadatos
LABEL maintainer="SAT System"
LABEL description="Procesador de datos de lluvia del IDEAM para sistema SAT"
LABEL version="1.0"

# Variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    git \
    wget \
    curl \
    build-essential \
    libgdal-dev \
    gdal-bin \
    libproj-dev \
    proj-data \
    proj-bin \
    libgeos-dev \
    libspatialindex-dev \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar archivos de requisitos
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY src/ ./src/

# Crear directorios necesarios
RUN mkdir -p /app/logs /app/data/output /app/data/input

# Establecer permisos
RUN chmod +x src/main.py

# Comando por defecto
CMD ["python", "src/main.py"]
