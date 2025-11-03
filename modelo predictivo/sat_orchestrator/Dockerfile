FROM python:3.12-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    cron \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Establecer directorio de trabajo
WORKDIR /app

# Copiar archivos de requisitos
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY src/ ./src/
COPY crontab /etc/cron.d/sat-orchestrator

# Configurar cron
RUN chmod 0644 /etc/cron.d/sat-orchestrator
RUN crontab /etc/cron.d/sat-orchestrator

# Crear directorios necesarios
RUN mkdir -p /app/logs

# Establecer variables de entorno
ENV PYTHONPATH=/app
ENV LOG_LEVEL=INFO

# Script de inicio que ejecuta cron y mantiene el contenedor activo
COPY start.sh /start.sh
RUN chmod +x /start.sh

# Comando por defecto
CMD ["/start.sh"]
