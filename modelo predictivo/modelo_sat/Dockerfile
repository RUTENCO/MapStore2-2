FROM python:3.9.21-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    libgdal-dev \
    libproj-dev \
    libgeos-dev \
    libspatialindex-dev \
    && rm -rf /var/lib/apt/lists/*

# Establecer directorio de trabajo
WORKDIR /app

# Copiar archivos de requisitos
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY src/ ./src/

# Crear directorios necesarios
RUN mkdir -p /app/logs /app/output /app/models

# Establecer variables de entorno
ENV PYTHONPATH=/app
ENV LOG_LEVEL=INFO

# Comando por defecto
CMD ["python", "src/main.py"]
