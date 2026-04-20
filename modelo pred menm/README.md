# Modelo Pred Menm

Este directorio contiene el modelo de predicción y su empaquetado para ejecución en contenedor. La integración está pensada para que el contenedor solo ejecute código y lea/escriba archivos en un volumen montado desde el servidor anfitrión.

## Estructura

```text
modelo pred menm/
├── docker-compose.yml
├── README.md
├── static/
│   └── datalake/
│       ├── cred/
│       ├── Geodata/
│       ├── img_results/
│       ├── logs/
│       └── models/
└── modelo/
    ├── Dockerfile
    ├── requirements.txt
    ├── src/
    │   ├── config.json
    │   └── main.py
    └── start.sh
```

## Cómo funciona

- `main.py` carga `config.json` desde la misma carpeta del script.
- Las rutas del `config.json` se resuelven contra `MODEL_DATA_ROOT`.
- El volumen del host se monta en `/data/datalake` dentro del contenedor.
- El contenedor ejecuta `main.py` mediante `cron` una vez al mes.
- Si se define `RUN_ON_START=true`, el modelo también corre al iniciar el contenedor.

## Requisitos de datos

Antes de arrancar el contenedor, debe existir esta estructura en el host:

```text
static/datalake/
├── cred/
│   └── geohazards-unal-firebase-adminsdk-i93jf-e7ca5cdae2.json
├── Geodata/
│   ├── geojson/
│   │   └── events.geojson
│   ├── raster/
│   │   ├── aspect.tif
│   │   ├── curvature.tif
│   │   ├── dem.tif
│   │   ├── geo.tif
│   │   └── slopes.tif
│   └── raster_results/
├── img_results/
├── logs/
└── models/
```

## Configuración

Los valores principales se controlan desde variables de entorno en `docker-compose.yml`:

- `MODEL_DATA_ROOT`: ruta base visible dentro del contenedor. Por defecto usa `/data/datalake`.
- `CRON_SCHEDULE`: expresión cron para programar la ejecución. Por defecto corre el día 1 de cada mes a las 00:00.
- `RUN_ON_START`: si vale `true`, ejecuta el modelo una vez al iniciar el contenedor.

El archivo `modelo/src/config.json` usa rutas relativas al datalake, por ejemplo `logs/`, `Geodata/raster/` y `models/`.

## Ejecución

### Con Docker Compose

Desde la carpeta raíz `modelo pred menm`:

```bash
docker compose up -d --build
```

Para ver la configuración renderizada:

```bash
docker compose config
```

### Ejecución manual dentro del contenedor

```bash
docker compose run --rm modelo-pred-menm
```

## Salidas esperadas

El modelo escribe resultados en el volumen montado, principalmente en:

- `static/datalake/logs/`
- `static/datalake/img_results/`
- `static/datalake/Geodata/raster_results/`
- `static/datalake/models/`

## Notas de despliegue

- La imagen no copia los datos al contenedor; solo copia el código.
- El contenedor asume que el host puede escribir en `static/datalake`.
- Si cambias la ubicación del volumen, ajusta `MODEL_DATA_ROOT` en `docker-compose.yml`.
