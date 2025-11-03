FROM python:3.12-slim

# Instalar dependencias del sistema incluyendo GDAL
RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    gcc \
    g++ \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Establecer variables de entorno para GDAL
ENV GDAL_CONFIG=/usr/bin/gdal-config
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

# Establecer directorio de trabajo
WORKDIR /app

# Copiar archivos de requisitos
COPY requirements.txt .

# Instalar GDAL Python bindings primero
RUN pip install --no-cache-dir GDAL==$(gdal-config --version)

# Instalar otras dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY src/ ./src/

# Crear directorios necesarios
RUN mkdir -p /app/logs /app/output

# Establecer variables de entorno
ENV PYTHONPATH=/app
ENV LOG_LEVEL=INFO

# Comando por defecto
CMD ["python", "src/main.py"]
