@echo off
echo ========================================
echo     Sistema SAT - Inicializacion
echo ========================================
echo.

REM Verificar que Docker Desktop esté ejecutándose
echo [1/6] Verificando Docker Desktop...
docker --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker Desktop no está ejecutándose o no está instalado.
    echo Por favor inicia Docker Desktop e intenta nuevamente.
    pause
    exit /b 1
)
echo ✓ Docker Desktop disponible

REM Verificar Docker Compose
echo [2/6] Verificando Docker Compose...
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker Compose no está disponible
    echo Por favor instala Docker Compose
    pause
    exit /b 1
)
echo ✓ Docker Compose disponible

REM Verificar archivos necesarios
echo [3/6] Verificando archivos necesarios...
if not exist "data\input\Region_andina_VivianaUrrea.shp" (
    echo ERROR: Archivo data\input\Region_andina_VivianaUrrea.shp no encontrado
    echo Este archivo es necesario para el funcionamiento del sistema
    pause
    exit /b 1
)
if not exist "data\input\estaciones_SAT_revis_nombres.shp" (
    echo ERROR: Archivo data\input\estaciones_SAT_revis_nombres.shp no encontrado
    echo Este archivo es necesario para el funcionamiento del sistema
    pause
    exit /b 1
)
if not exist "docker-compose.yml" (
    echo ERROR: Archivo docker-compose.yml no encontrado
    pause
    exit /b 1
)
if not exist ".env" (
    echo ERROR: Archivo .env no encontrado
    pause
    exit /b 1
)
echo ✓ Todos los archivos necesarios están presentes

REM Crear estructura de directorios
echo [4/6] Creando estructura de directorios...
mkdir data\input 2>nul
mkdir data\output\lluvia 2>nul
mkdir data\output\modelo 2>nul
mkdir data\output\geotiff 2>nul
mkdir logs 2>nul

REM Los archivos shapefile ya están en data\input\ y se montan como volúmenes
echo Archivos shapefile disponibles en data\input\ para uso compartido...
echo ✓ Estructura de directorios creada

REM Construir imágenes Docker
echo [5/6] Construyendo imágenes Docker...
echo Este proceso puede tomar varios minutos...
docker-compose build
if errorlevel 1 (
    echo ERROR: Falló la construcción de las imágenes Docker
    echo Revisa los logs anteriores para más detalles
    pause
    exit /b 1
)
echo ✓ Imágenes Docker construidas exitosamente

REM Verificar imágenes creadas
echo [6/6] Verificando imágenes creadas...
docker images | findstr sat_system >nul 2>&1
if errorlevel 1 (
    echo ADVERTENCIA: No se encontraron todas las imágenes esperadas
) else (
    echo ✓ Todas las imágenes Docker están disponibles
)

echo.
echo ========================================
echo   INICIALIZACION COMPLETADA EXITOSAMENTE
echo ========================================
echo.
echo El sistema SAT está listo para usar.
echo.
echo COMANDOS DISPONIBLES:
echo.
echo   Pipeline completo:
echo   docker-compose up
echo.
echo   Solo procesamiento de lluvia:
echo   docker-compose run --rm lluvia-processor
echo.
echo   Solo modelo de prediccion:
echo   docker-compose run --rm modelo-sat
echo.
echo   Solo exportacion GeoTIFF:
echo   docker-compose run --rm geotiff-exporter
echo.
echo   Monitoreo continuo (cron):
echo   docker-compose up sat-orchestrator
echo.
echo   Ver estado del sistema:
echo   docker-compose run --rm sat-orchestrator python src/orchestrator.py --mode status
echo.
echo Para más información consulta el archivo README.md
echo.
pause
