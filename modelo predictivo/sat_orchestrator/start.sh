#!/bin/bash

# Iniciar cron en segundo plano
cron

# Log de inicio
echo "$(date): SAT Orchestrator iniciado" >> /app/logs/orchestrator.log

# Ejecutar una vez al inicio (opcional)
if [ "$RUN_ON_START" = "true" ]; then
    echo "$(date): Ejecutando pipeline inicial" >> /app/logs/orchestrator.log
    python /app/src/orchestrator.py --mode full
fi

# Mantener el contenedor corriendo
tail -f /app/logs/orchestrator.log /app/logs/cron.log
