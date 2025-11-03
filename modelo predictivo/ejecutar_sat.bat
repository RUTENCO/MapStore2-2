@echo off
echo ========================================
echo     Sistema SAT - Ejecucion Rapida
echo ========================================
echo.

REM Mostrar opciones
echo Selecciona el tipo de ejecución:
echo.
echo 1. Pipeline completo (lluvia + modelo + geotiff)
echo 2. Solo procesamiento de lluvia
echo 3. Solo modelo de predicción
echo 4. Solo exportación GeoTIFF
echo 5. Pipeline parcial (modelo + geotiff)
echo 6. Monitoreo continuo (cron)
echo 7. Ver estado del sistema
echo 8. Ver logs en tiempo real
echo 9. Limpiar y reiniciar
echo 0. Salir
echo.

set /p opcion="Ingresa tu opción (0-9): "

if "%opcion%"=="1" goto pipeline_completo
if "%opcion%"=="2" goto solo_lluvia
if "%opcion%"=="3" goto solo_modelo
if "%opcion%"=="4" goto solo_geotiff
if "%opcion%"=="5" goto pipeline_parcial
if "%opcion%"=="6" goto monitoreo
if "%opcion%"=="7" goto estado
if "%opcion%"=="8" goto logs
if "%opcion%"=="9" goto limpiar
if "%opcion%"=="0" goto salir

echo Opción inválida
goto fin

:pipeline_completo
echo.
echo Ejecutando pipeline completo...
echo Esto puede tomar 15-30 minutos dependiendo de la conectividad
echo Este comando ejecutara los servicios de forma coordinada y secuencial
echo.
docker-compose run --rm sat-orchestrator python src/orchestrator.py --mode full
goto fin

:solo_lluvia
echo.
echo Ejecutando solo procesamiento de lluvia...
echo.
docker-compose run --rm lluvia-processor
goto fin

:solo_modelo
echo.
echo Ejecutando solo modelo de predicción...
echo.
docker-compose run --rm modelo-sat
goto fin

:solo_geotiff
echo.
echo Ejecutando solo exportación GeoTIFF...
echo.
docker-compose run --rm geotiff-exporter
goto fin

:pipeline_parcial
echo.
echo Ejecutando pipeline parcial (modelo + geotiff)...
echo.
docker-compose run --rm sat-orchestrator python src/orchestrator.py --mode partial
goto fin

:monitoreo
echo.
echo Iniciando monitoreo continuo...
echo El sistema ejecutará automáticamente según programación
echo Pipeline completo: diario a las 06:00
echo Pipeline parcial: cada 6 horas
echo.
echo Presiona Ctrl+C para detener
echo.
docker-compose up sat-orchestrator
goto fin

:estado
echo.
echo Obteniendo estado del sistema...
echo.
docker-compose run --rm sat-orchestrator python src/orchestrator.py --mode status
goto fin

:logs
echo.
echo Mostrando logs en tiempo real...
echo Presiona Ctrl+C para detener
echo.
docker-compose logs -f --tail=50
goto fin

:limpiar
echo.
echo Limpiando y reiniciando sistema...
echo.
docker-compose down
docker-compose down -v
echo Sistema limpiado. Ejecuta 'inicializar_sat.bat' para reinicializar.
goto fin

:salir
echo.
echo Saliendo...
goto fin

:fin
echo.
echo ========================================
echo Presiona cualquier tecla para continuar...
pause >nul
