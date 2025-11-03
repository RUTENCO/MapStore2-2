# Sistema Integrado SAT + MapStore

Sistema completo que integra el pipeline SAT (Sistema de Alerta Temprana) con MapStore/GeoServer para visualización automática de predicciones de deslizamientos.

## Componentes

### Stack SAT
- **lluvia-processor**: Descarga datos de lluvia de IDEAM
- **modelo-sat**: Ejecuta modelo predictivo de deslizamientos  
- **geotiff-exporter**: Genera GeoTIFF y lo copia automáticamente a GeoServer
- **sat-orchestrator**: Orquesta ejecución automática diaria (8:10 PM)

### Stack MapStore
- **postgres**: Base de datos PostGIS
- **geoserver**: Servidor de mapas (puerto 8081)
- **mapstore**: Aplicación de mapas (puerto 8080)
- **proxy**: Nginx reverse proxy (puerto 80)

## Características Clave

✅ **Actualización automática**: El GeoTIFF se genera como `prob_geotif.tif` y se sobreescribe diariamente  
✅ **Integración transparente**: Volumen compartido `geoserver_uploads` entre SAT y GeoServer  
✅ **Ejecución programada**: Cron automático a las 8:10 PM todos los días  
✅ **Stack completo**: Una sola configuración para todo el sistema  

## Uso

### 1. Levantar Stack MapStore (Base)
```bash
# Solo MapStore + GeoServer + DB + Proxy
docker-compose -f docker-compose3.yml up -d postgres geoserver mapstore proxy
```

### 2. Levantar SAT con Orquestador (Completo)
```bash
# Stack completo con pipeline SAT automatizado
docker-compose -f docker-compose3.yml --profile orchestrator --profile full-pipeline up -d
```

### 3. Ejecutar Pipeline SAT Manualmente (Opcional)
```bash
# Solo ejecución manual del pipeline
docker-compose -f docker-compose3.yml --profile full-pipeline up lluvia-processor modelo-sat geotiff-exporter
```

## URLs de Acceso

- **MapStore**: http://localhost:8080 (o http://localhost)
- **GeoServer**: http://localhost:8081/geoserver
  - Usuario: `admin` / Contraseña: `geoserver`
- **Base de datos**: localhost:5432
  - Usuario: `postgres` / Contraseña: `postgres` / DB: `geostore`

## Flujo Automático

1. **8:10 PM diario**: Orchestrator ejecuta pipeline SAT
2. **lluvia-processor**: Descarga datos IDEAM (30-45 min)
3. **modelo-sat**: Ejecuta predicciones (~5 seg)
4. **geotiff-exporter**: Genera y copia `prob_geotif.tif` a GeoServer (~15 seg)
5. **GeoServer**: Detecta automáticamente el archivo actualizado
6. **MapStore**: Muestra la nueva predicción sin reconfiguración

## Archivos Generados

### En volumen `geoserver_uploads`:
- `prob_geotif.tif` - GeoTIFF con predicciones (se actualiza diariamente)

### En directorios locales:
- `data/output/lluvia/` - Datos de lluvia procesados
- `data/output/modelo/` - Predicciones en formato GPKG/CSV  
- `data/output/geotiff/` - GeoTIFF original
- `logs/` - Logs de todos los servicios

## Variables de Entorno

Crear archivo `.env` con:
```env
# IDEAM API
IDEAM_API_TOKEN=tu_token_aqui
DAYS_BACK=30

# Configuración SAT
LOG_LEVEL=INFO
INTERPOLATION_METHOD=idw
PIXEL_SIZE=2000
IDW_POWER=3

# Orquestador  
CRON_SCHEDULE=10 01 * * *
RUN_ON_START=false
```

## Troubleshooting

```bash
# Ver logs del pipeline
docker-compose -f docker-compose3.yml logs -f lluvia-processor modelo-sat geotiff-exporter

# Ver logs del orquestador
docker-compose -f docker-compose3.yml logs -f sat-orchestrator

# Verificar volúmenes
docker volume ls | grep sat_mapstore_system

# Estado de servicios
docker-compose -f docker-compose3.yml ps
```

## Desarrollo

Para desarrollo local, puedes ejecutar servicios individualmente:

```bash
# Solo pipeline SAT
docker-compose -f docker-compose3.yml --profile full-pipeline up

# Solo MapStore stack  
docker-compose -f docker-compose3.yml up postgres geoserver mapstore

# Ejecutar test de un servicio específico
docker-compose -f docker-compose3.yml run --rm geotiff-exporter
```
