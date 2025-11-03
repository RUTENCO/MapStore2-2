# Sistema SAT - Pipeline de Predicción de Deslizamientos

Este proyecto implementa un sistema completo para la predicción de deslizamientos de tierra usando datos de lluvia del IDEAM, modelos de Machine Learning y generación de mapas de riesgo en formato GeoTIFF.

## 🏗️ Arquitectura del Sistema

El sistema SAT está compuesto por 4 servicios principales ejecutándose en contenedores Docker:

### 📊 **Flujo de Datos**
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  🌧️ Lluvia     │───▶│  🤖 Modelo      │───▶│  🗺️ GeoTIFF    │
│  Processor      │    │  SAT            │    │  Exporter       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
📄 lluvia_procesada      📄 predicciones_sat    📄 mapa_riesgo
   _latest.csv             _latest.gpkg           _latest.tif
```

### 1. **Lluvia Processor** (`lluvia_processor`)
- **Función**: Descarga y procesa datos de lluvia de las últimas 24h, 7 días y 30 días desde la API del IDEAM
- **Entrada**: Estaciones meteorológicas (shapefile), token IDEAM
- **Salida**: Dataset con acumulados de lluvia por estación (`lluvia_procesada_latest.csv`)
- **Tecnología**: Python 3.12, GeoPandas, requests

### 2. **Modelo SAT** (`modelo_sat`)
- **Función**: Ejecuta modelo de Machine Learning para calcular probabilidades de deslizamiento
- **Entrada**: Datos de lluvia procesados
- **Salida**: Predicciones con probabilidades por estación (`predicciones_sat_latest.csv/gpkg`)
- **Tecnología**: Python 3.9.21, scikit-learn, Random Forest

### 3. **GeoTIFF Exporter** (`geotiff_exporter`)
- **Función**: Interpola probabilidades puntuales a superficie continua usando IDW
- **Entrada**: Predicciones del modelo, región andina (shapefile)
- **Salida**: Mapa de riesgo en formato GeoTIFF (`probabilidad_deslizamientos_latest.tif`)
- **Tecnología**: Python 3.12, Rasterio, GDAL, SciPy

### 4. **SAT Orchestrator** (`sat_orchestrator`)
- **Función**: Coordina la ejecución secuencial del pipeline y maneja la programación
- **Entrada**: Configuración de horarios (cron)
- **Salida**: Logs de ejecución y monitoreo del sistema
- **Tecnología**: Python 3.12, Docker API, Cron

## 🚀 Instalación y Configuración

### Prerrequisitos
- Docker Desktop instalado
- Docker Compose v2
- Mínimo 4GB RAM disponible
- 2GB espacio en disco

### 1. Clonar y Preparar Archivos

```bash
# Navegar al directorio del proyecto
cd c:\Users\estiv\Downloads\modelo predictivo

# Verificar que están todos los archivos necesarios
dir
```

**Archivos requeridos:**
- `data/input/Region_andina_VivianaUrrea.shp` (+ .dbf, .prj, .shx)
- `data/input/estaciones_SAT_revis_nombres.shp` (+ .dbf, .prj, .shx)
- `docker-compose.yml` (en directorio raíz)
- `.env` (en directorio raíz)

### 2. Configurar Variables de Entorno

Editar el archivo `.env` según sea necesario:

```env
# Token de API IDEAM
IDEAM_TOKEN=VHmxDK45cRdGqCp2XBnesQVWQ

# Configuración de logging
LOG_LEVEL=INFO

# Configuración de interpolación
PIXEL_SIZE=0.01
BUFFER_DISTANCE=0.05

# Ejecutar pipeline al iniciar
RUN_ON_START=false

# URL del modelo pre-entrenado (opcional)
MODEL_URL=
```

### 3. Construcción de Contenedores

```bash
# Construir todos los servicios
docker-compose build

# Verificar que las imágenes se crearon
docker images | findstr sat-pipeline
```

### 4. Preparar Datos de Entrada

Los archivos shapefile ya deben estar ubicados en `data/input/`. El script de inicialización se encargará de copiarlos automáticamente a cada servicio.

**Estructura esperada:**
```
data/
└── input/
    ├── Region_andina_VivianaUrrea.shp
    ├── Region_andina_VivianaUrrea.dbf
    ├── Region_andina_VivianaUrrea.prj
    ├── Region_andina_VivianaUrrea.shx
    ├── estaciones_SAT_revis_nombres.shp
    ├── estaciones_SAT_revis_nombres.dbf
    ├── estaciones_SAT_revis_nombres.prj
    └── estaciones_SAT_revis_nombres.shx
```

## 🎯 Uso del Sistema

### Ejecución Manual Completa

```bash
# Ejecutar pipeline completo (lluvia → modelo → geotiff)
docker-compose up

# Ver logs en tiempo real
docker-compose logs -f
```

### Ejecución de Servicios Individuales

```bash
# Solo procesamiento de lluvia
docker-compose run --rm lluvia-processor

# Solo modelo de predicción
docker-compose run --rm modelo-sat

# Solo exportación GeoTIFF
docker-compose run --rm geotiff-exporter

# Solo orquestador (manual)
docker-compose run --rm sat-orchestrator python src/orchestrator.py --mode full
```

### Modo de Monitoreo Continuo

```bash
# Iniciar orquestador con programación automática
docker-compose up sat-orchestrator

# El sistema ejecutará:
# - Pipeline completo diario a las 06:00
# - Pipeline parcial (modelo + geotiff) cada 6 horas
```

### Comandos de Administración

```bash
# Ver estado de todos los servicios
docker-compose run --rm sat-orchestrator python src/orchestrator.py --mode status

# Ejecutar servicio específico
docker-compose run --rm sat-orchestrator python src/orchestrator.py --service lluvia-processor

# Ver logs de un servicio específico
docker-compose logs lluvia-processor

# Detener todos los servicios
docker-compose down

# Limpiar volúmenes (⚠️ elimina todos los datos)
docker-compose down -v
```

## 📊 Resultados y Archivos de Salida

### Estructura de Archivos Generados

```
data/
├── input/                    # Archivos de entrada (shapefiles)
│   ├── Region_andina_VivianaUrrea.shp
│   ├── Region_andina_VivianaUrrea.dbf
│   ├── Region_andina_VivianaUrrea.prj
│   ├── Region_andina_VivianaUrrea.shx
│   ├── estaciones_SAT_revis_nombres.shp
│   ├── estaciones_SAT_revis_nombres.dbf
│   ├── estaciones_SAT_revis_nombres.prj
│   └── estaciones_SAT_revis_nombres.shx
└── output/                   # Archivos generados por el sistema
    ├── lluvia/
    │   ├── lluvia_procesada_YYYYMMDD_HHMMSS.csv
    │   ├── lluvia_procesada_latest.csv
    │   └── resumen_lluvia.json
    ├── modelo/
    │   ├── predicciones_sat_YYYYMMDD_HHMMSS.csv
    │   ├── predicciones_sat_latest.csv
    │   ├── predicciones_sat_latest.gpkg
    │   └── estadisticas_modelo.json
    └── geotiff/
        ├── probabilidad_deslizamientos_YYYYMMDD_HHMMSS.tif
        ├── probabilidad_deslizamientos_latest.tif
        ├── visualizacion_riesgo_latest.png
        └── estadisticas_geotiff.json
logs/                         # Logs del sistema
├── lluvia_processor.log
├── modelo_sat.log
├── geotiff_exporter.log
├── orchestrator.log
└── ejecucion_YYYYMMDD_HHMMSS.json
```

### Interpretación de Resultados

#### Niveles de Riesgo
- **ALTO** (≥0.7): Rojo - Probabilidad alta de deslizamiento
- **MEDIO-ALTO** (0.5-0.69): Naranja - Riesgo considerable
- **MEDIO** (0.3-0.49): Amarillo - Riesgo moderado
- **BAJO-MEDIO** (0.1-0.29): Verde claro - Riesgo bajo-moderado
- **BAJO** (<0.1): Verde - Riesgo mínimo

#### Archivos Principales
- **`probabilidad_deslizamientos_latest.tif`**: Mapa raster final para análisis SIG
- **`predicciones_sat_latest.csv`**: Datos tabulares con probabilidades por estación
- **`visualizacion_riesgo_latest.png`**: Mapa visual del riesgo

## 🔧 Configuración Avanzada

### Personalizar Horarios de Ejecución

Editar `sat_orchestrator/crontab`:

```cron
# Ejecutar cada hora durante temporada de lluvias
0 * * * * /usr/local/bin/python /app/src/orchestrator.py --mode partial

# Ejecutar pipeline completo cada 12 horas
0 */12 * * * /usr/local/bin/python /app/src/orchestrator.py --mode full
```

### Configurar Resolución de Interpolación

En `.env`:

```env
# Resolución más alta (más detalle, más lento)
PIXEL_SIZE=0.005  # ~500m

# Resolución más baja (menos detalle, más rápido)
PIXEL_SIZE=0.02   # ~2km
```

### Añadir Modelo Pre-entrenado

```env
# URL de modelo pre-entrenado
MODEL_URL=https://ejemplo.com/modelo_sat_rf.pkl
```

### Configurar Logging Detallado

```env
# Nivel de logging más detallado
LOG_LEVEL=DEBUG
```

## 🐛 Resolución de Problemas

### Problemas Comunes

#### 1. Error "Archivos shapefile no encontrados"
```bash
# Verificar que los archivos están en el lugar correcto
dir lluvia_processor\data\*.shp
dir modelo_sat\data\*.shp
dir geotiff_exporter\data\*.shp
```

#### 2. Error de conexión con API IDEAM
```bash
# Verificar token en .env
echo %IDEAM_TOKEN%

# Probar conexión manual
curl "https://dhime.ideam.gov.co/atenea/?token=VHmxDK45cRdGqCp2XBnesQVWQ&format=json"
```

#### 3. Contenedor se detiene inmediatamente
```bash
# Ver logs detallados
docker-compose logs lluvia-processor

# Ejecutar en modo interactivo para debugging
docker-compose run --rm lluvia-processor bash
```

#### 4. Problemas de memoria/rendimiento
```bash
# Verificar recursos disponibles
docker system df
docker stats

# Ajustar límites en docker-compose.yml
```

### Logs y Debugging

```bash
# Ver todos los logs
docker-compose logs

# Seguir logs en tiempo real
docker-compose logs -f --tail=100

# Logs de un servicio específico
docker-compose logs lluvia-processor

# Entrar a un contenedor para debugging
docker-compose exec lluvia-processor bash
```

### Monitoreo del Sistema

```bash
# Estado de contenedores
docker-compose ps

# Uso de recursos
docker stats $(docker-compose ps -q)

# Espacio en disco
docker system df

# Limpiar recursos no utilizados
docker system prune
```

## 📈 Monitoreo y Mantenimiento

### Verificación de Salud del Sistema

```bash
# Script de verificación diaria
docker-compose run --rm sat-orchestrator python src/orchestrator.py --mode status

# Verificar archivos de salida recientes
dir data\output\geotiff\*latest*

# Verificar logs por errores
findstr /i "error" logs\*.log
```

### Respaldo de Datos

```bash
# Respaldar datos importantes
xcopy data\output backup\data_YYYYMMDD /E /I

# Respaldar logs
xcopy logs backup\logs_YYYYMMDD /E /I
```

### Limpieza Automática

Crear script `cleanup.bat`:

```batch
@echo off
echo Limpiando archivos antiguos...

# Eliminar archivos de más de 30 días
forfiles /p data\output /r /m *.* /d -30 /c "cmd /c del @path"

# Limpiar logs antiguos
forfiles /p logs /r /m *.log /d -7 /c "cmd /c del @path"

echo Limpieza completada
```

## 🔒 Consideraciones de Seguridad

1. **Token IDEAM**: Mantener el token seguro y rotarlo periódicamente
2. **Acceso a archivos**: Configurar permisos apropiados en directorios de datos
3. **Actualizaciones**: Mantener imágenes Docker actualizadas
4. **Monitoreo**: Configurar alertas para fallos del sistema

## 📞 Soporte y Contacto

Para problemas técnicos o mejoras al sistema:

1. Revisar logs del sistema
2. Consultar esta documentación
3. Verificar configuración de Docker y variables de entorno
4. Contactar al equipo de desarrollo con logs específicos

---

**Sistema SAT - Pipeline de Predicción de Deslizamientos**  
*Versión Dockerizada para Producción*
