#!/usr/bin/env python3
"""
SAT Pipeline - Orchestrator Service
Servicio para coordinar la ejecución del pipeline completo SAT
"""

import os
import sys
import logging
import argparse
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
import docker
import requests
import yaml

# Configuración de logging
def setup_logging():
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('/app/logs/orchestrator.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

class SATOrchestrator:
    def __init__(self):
        self.docker_client = docker.from_env()
        self.compose_project = os.getenv('COMPOSE_PROJECT_NAME', 'sat_system')
        
        # Configuración de servicios (sin timeouts - espera indefinida)
        # Usando los nombres reales de los contenedores tal como aparecen en docker ps
        self.services = {
            'lluvia-processor': {
                'name': 'sat_lluvia_processor'
            },
            'modelo-sat': {
                'name': 'sat_modelo_deslizamientos'
            },
            'geotiff-exporter': {
                'name': 'sat_geotiff_exporter'
            }
        }
        
        logger.info("SATOrchestrator inicializado")
        logger.info(f"Proyecto Docker Compose: {self.compose_project}")

    def verificar_servicios_disponibles(self):
        """Verifica que todos los servicios estén disponibles"""
        servicios_disponibles = []
        
        try:
            containers = self.docker_client.containers.list(all=True)
            container_names = [c.name for c in containers]
            
            for service_key, service_info in self.services.items():
                if service_info['name'] in container_names:
                    servicios_disponibles.append(service_key)
                    logger.info(f"✓ Servicio disponible: {service_key}")
                else:
                    logger.warning(f"⚠ Servicio no encontrado: {service_key} ({service_info['name']})")
            
            return servicios_disponibles
            
        except Exception as e:
            logger.error(f"Error verificando servicios: {e}")
            return []

    def obtener_container(self, service_key):
        """Obtiene el contenedor de un servicio"""
        try:
            service_info = self.services[service_key]
            container = self.docker_client.containers.get(service_info['name'])
            return container
        except docker.errors.NotFound:
            logger.error(f"Contenedor no encontrado: {service_info['name']}")
            return None
        except Exception as e:
            logger.error(f"Error obteniendo contenedor {service_key}: {e}")
            return None

    def obtener_estado_contenedor_robusto(self, container, service_key):
        """Obtiene el estado del contenedor de manera robusta, manejando errores de Docker daemon"""
        max_reintentos = 3
        for intento in range(max_reintentos):
            try:
                container.reload()
                return container.status, container.attrs['State']['ExitCode'] if container.status == 'exited' else None
            except Exception as e:
                logger.warning(f"Error obteniendo estado del contenedor {service_key} (intento {intento + 1}/{max_reintentos}): {e}")
                if intento < max_reintentos - 1:
                    time.sleep(5)  # Esperar antes del siguiente intento
                else:
                    # Último intento: verificar usando docker ps como respaldo
                    try:
                        # Buscar el contenedor usando docker client de manera alternativa
                        containers = self.docker_client.containers.list(all=True, filters={"name": self.services[service_key]['name']})
                        if containers:
                            alt_container = containers[0]
                            return alt_container.status, alt_container.attrs['State']['ExitCode'] if alt_container.status == 'exited' else None
                    except Exception as e2:
                        logger.error(f"Error crítico obteniendo estado del contenedor {service_key}: {e2}")
                        return None, None
        return None, None

    def ejecutar_servicio(self, service_key, wait_for_completion=True):
        """Ejecuta un servicio específico"""
        logger.info(f"=== Ejecutando servicio: {service_key} ===")
        
        try:
            container = self.obtener_container(service_key)
            if not container:
                return False, f"Contenedor {service_key} no disponible"
            
            # Verificar estado del contenedor de manera robusta
            status, exit_code = self.obtener_estado_contenedor_robusto(container, service_key)
            if status is None:
                return False, "No se pudo obtener estado del contenedor"
                
            if status == 'running':
                logger.info(f"Contenedor {service_key} ya está ejecutándose")
                if not wait_for_completion:
                    return True, "Servicio ejecutándose"
            else:
                # Iniciar contenedor
                logger.info(f"Iniciando contenedor {service_key}")
                container.start()
                time.sleep(5)  # Dar tiempo para iniciar
            
            if wait_for_completion:
                # Esperar a que termine (sin timeout - tiempo indefinido)
                logger.info(f"Esperando completación del servicio {service_key} (sin límite de tiempo)")
                
                while True:
                    status, exit_code = self.obtener_estado_contenedor_robusto(container, service_key)
                    
                    if status is None:
                        logger.error(f"No se pudo obtener estado del contenedor {service_key}")
                        return False, "Error de conectividad con Docker daemon"
                    
                    if status == 'exited':
                        # Verificar código de salida
                        if exit_code == 0:
                            logger.info(f"✓ Servicio {service_key} completado exitosamente")
                            return True, "Completado exitosamente"
                        else:
                            # Obtener logs de error
                            try:
                                logs = container.logs(tail=50).decode('utf-8')
                                logger.error(f"✗ Servicio {service_key} falló (exit code: {exit_code})")
                                logger.error(f"Logs del error:\n{logs}")
                            except:
                                logger.error(f"✗ Servicio {service_key} falló (exit code: {exit_code}) - No se pudieron obtener logs")
                            return False, f"Falló con código {exit_code}"
                    
                    elif status != 'running':
                        logger.error(f"Contenedor {service_key} en estado inesperado: {status}")
                        return False, f"Estado inesperado: {status}"
                    
                    time.sleep(10)  # Verificar cada 10 segundos
            
            else:
                return True, "Servicio iniciado"
                
        except Exception as e:
            logger.error(f"Error ejecutando servicio {service_key}: {e}")
            return False, str(e)

    def verificar_flujo_datos(self, service_key):
        """Verifica que los datos de salida estén disponibles para el siguiente servicio"""
        try:
            data_path = Path('/app/data')
            
            if service_key == 'lluvia-processor':
                # Verificar que hay datos de lluvia
                lluvia_files = list((data_path / 'output' / 'lluvia').glob('*.csv'))
                latest_file = data_path / 'output' / 'lluvia' / 'lluvia_procesada_latest.csv'
                
                if latest_file.exists() or lluvia_files:
                    logger.info("✓ Datos de lluvia disponibles")
                    return True
                else:
                    logger.error("✗ No hay datos de lluvia disponibles")
                    return False
            
            elif service_key == 'modelo-sat':
                # Verificar que hay predicciones (nombres reales que generamos)
                modelo_files = list((data_path / 'output' / 'modelo').glob('*.csv'))
                csv_file = data_path / 'output' / 'modelo' / 'prob_deslizamientos.csv'
                gpkg_file = data_path / 'output' / 'modelo' / 'prob_deslizamientos.gpkg'
                
                if csv_file.exists() or gpkg_file.exists() or modelo_files:
                    logger.info("✓ Predicciones del modelo disponibles")
                    return True
                else:
                    logger.error("✗ No hay predicciones del modelo disponibles")
                    return False
            
            elif service_key == 'geotiff-exporter':
                # Verificar que hay GeoTIFF (nombre real que generamos)
                geotiff_files = list((data_path / 'output' / 'geotiff').glob('*.tif'))
                geotiff_file = data_path / 'output' / 'geotiff' / 'prob_geotif.tif'
                
                if geotiff_file.exists() or geotiff_files:
                    logger.info("✓ GeoTIFF de salida disponible")
                    return True
                else:
                    logger.error("✗ No hay GeoTIFF de salida disponible")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error verificando flujo de datos para {service_key}: {e}")
            return False

    def ejecutar_pipeline_completo(self):
        """Ejecuta el pipeline completo: lluvia -> modelo -> geotiff"""
        logger.info("=== INICIANDO PIPELINE COMPLETO SAT ===")
        
        pipeline_start = time.time()
        resultados = {
            'timestamp_inicio': datetime.now().isoformat(),
            'servicios_ejecutados': [],
            'exitoso': False,
            'duracion_total': 0,
            'errores': []
        }
        
        # Secuencia de servicios
        secuencia = ['lluvia-processor', 'modelo-sat', 'geotiff-exporter']
        
        try:
            # Verificar servicios disponibles
            servicios_disponibles = self.verificar_servicios_disponibles()
            servicios_faltantes = [s for s in secuencia if s not in servicios_disponibles]
            
            if servicios_faltantes:
                error_msg = f"Servicios no disponibles: {servicios_faltantes}"
                logger.error(error_msg)
                resultados['errores'].append(error_msg)
                return resultados
            
            # Ejecutar cada servicio en secuencia
            for service_key in secuencia:
                service_start = time.time()
                logger.info(f"\n--- Paso {len(resultados['servicios_ejecutados']) + 1}: {service_key} ---")
                
                # Ejecutar servicio
                exito, mensaje = self.ejecutar_servicio(service_key, wait_for_completion=True)
                service_duration = time.time() - service_start
                
                # Registrar resultado
                resultado_servicio = {
                    'servicio': service_key,
                    'exitoso': exito,
                    'mensaje': mensaje,
                    'duracion': round(service_duration, 2),
                    'timestamp': datetime.now().isoformat()
                }
                resultados['servicios_ejecutados'].append(resultado_servicio)
                
                if not exito:
                    error_msg = f"Servicio {service_key} falló: {mensaje}"
                    logger.error(error_msg)
                    resultados['errores'].append(error_msg)
                    break
                
                # Verificar flujo de datos
                if not self.verificar_flujo_datos(service_key):
                    error_msg = f"Verificación de datos falló para {service_key}"
                    logger.error(error_msg)
                    resultados['errores'].append(error_msg)
                    break
                
                logger.info(f"✓ {service_key} completado en {service_duration:.1f}s")
            
            # Verificar si todo fue exitoso
            if len(resultados['servicios_ejecutados']) == len(secuencia):
                todos_exitosos = all(r['exitoso'] for r in resultados['servicios_ejecutados'])
                if todos_exitosos:
                    resultados['exitoso'] = True
                    logger.info("🎉 PIPELINE COMPLETO EJECUTADO EXITOSAMENTE")
                else:
                    logger.error("❌ Pipeline completado con errores")
            else:
                logger.error("❌ Pipeline incompleto")
            
        except Exception as e:
            error_msg = f"Error fatal en pipeline: {e}"
            logger.error(error_msg)
            resultados['errores'].append(error_msg)
        
        finally:
            resultados['duracion_total'] = round(time.time() - pipeline_start, 2)
            resultados['timestamp_fin'] = datetime.now().isoformat()
            
            # Guardar resultados
            self.guardar_resultados_ejecucion(resultados)
            
            logger.info(f"Pipeline completado en {resultados['duracion_total']}s")
            return resultados

    def ejecutar_pipeline_parcial(self):
        """Ejecuta solo modelo y geotiff (asume que hay datos de lluvia)"""
        logger.info("=== INICIANDO PIPELINE PARCIAL SAT ===")
        
        # Verificar que hay datos de lluvia
        if not self.verificar_flujo_datos('lluvia-processor'):
            logger.error("No hay datos de lluvia disponibles para pipeline parcial")
            return {
                'exitoso': False,
                'error': 'No hay datos de lluvia disponibles'
            }
        
        # Ejecutar solo modelo y geotiff
        secuencia_parcial = ['modelo-sat', 'geotiff-exporter']
        
        resultados = {
            'timestamp_inicio': datetime.now().isoformat(),
            'modo': 'parcial',
            'servicios_ejecutados': [],
            'exitoso': False,
            'duracion_total': 0,
            'errores': []
        }
        
        pipeline_start = time.time()
        
        try:
            for service_key in secuencia_parcial:
                service_start = time.time()
                logger.info(f"\n--- Ejecutando: {service_key} ---")
                
                exito, mensaje = self.ejecutar_servicio(service_key, wait_for_completion=True)
                service_duration = time.time() - service_start
                
                resultado_servicio = {
                    'servicio': service_key,
                    'exitoso': exito,
                    'mensaje': mensaje,
                    'duracion': round(service_duration, 2),
                    'timestamp': datetime.now().isoformat()
                }
                resultados['servicios_ejecutados'].append(resultado_servicio)
                
                if not exito:
                    error_msg = f"Servicio {service_key} falló: {mensaje}"
                    logger.error(error_msg)
                    resultados['errores'].append(error_msg)
                    break
                
                logger.info(f"✓ {service_key} completado en {service_duration:.1f}s")
            
            # Verificar éxito
            if len(resultados['servicios_ejecutados']) == len(secuencia_parcial):
                todos_exitosos = all(r['exitoso'] for r in resultados['servicios_ejecutados'])
                if todos_exitosos:
                    resultados['exitoso'] = True
                    logger.info("🎉 PIPELINE PARCIAL EJECUTADO EXITOSAMENTE")
        
        except Exception as e:
            error_msg = f"Error en pipeline parcial: {e}"
            logger.error(error_msg)
            resultados['errores'].append(error_msg)
        
        finally:
            resultados['duracion_total'] = round(time.time() - pipeline_start, 2)
            resultados['timestamp_fin'] = datetime.now().isoformat()
            
            self.guardar_resultados_ejecucion(resultados)
            logger.info(f"Pipeline parcial completado en {resultados['duracion_total']}s")
            
        return resultados

    def guardar_resultados_ejecucion(self, resultados):
        """Guarda los resultados de la ejecución"""
        try:
            logs_path = Path('/app/logs')
            logs_path.mkdir(parents=True, exist_ok=True)
            
            # Archivo con timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            archivo_resultado = logs_path / f'ejecucion_{timestamp}.json'
            
            with open(archivo_resultado, 'w', encoding='utf-8') as f:
                json.dump(resultados, f, indent=2, ensure_ascii=False)
            
            # Último resultado
            archivo_ultimo = logs_path / 'ultima_ejecucion.json'
            with open(archivo_ultimo, 'w', encoding='utf-8') as f:
                json.dump(resultados, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Resultados guardados en: {archivo_ultimo}")
            
        except Exception as e:
            logger.error(f"Error guardando resultados: {e}")

    def obtener_estado_servicios(self):
        """Obtiene el estado actual de todos los servicios"""
        try:
            estado = {
                'timestamp': datetime.now().isoformat(),
                'servicios': {}
            }
            
            for service_key, service_info in self.services.items():
                try:
                    container = self.obtener_container(service_key)
                    if container:
                        container.reload()
                        estado['servicios'][service_key] = {
                            'estado': container.status,
                            'nombre_contenedor': container.name,
                            'disponible': True
                        }
                    else:
                        estado['servicios'][service_key] = {
                            'estado': 'no_encontrado',
                            'disponible': False
                        }
                except Exception as e:
                    estado['servicios'][service_key] = {
                        'estado': 'error',
                        'error': str(e),
                        'disponible': False
                    }
            
            return estado
            
        except Exception as e:
            logger.error(f"Error obteniendo estado de servicios: {e}")
            return {'error': str(e)}

def main():
    """Función principal del orquestador"""
    parser = argparse.ArgumentParser(description='SAT Pipeline Orchestrator')
    parser.add_argument('--mode', choices=['full', 'partial', 'status'], 
                       default='full', help='Modo de ejecución')
    parser.add_argument('--service', help='Ejecutar servicio específico')
    
    args = parser.parse_args()
    
    logger.info("=== SAT ORCHESTRATOR INICIADO ===")
    logger.info(f"Modo: {args.mode}")
    
    try:
        orchestrator = SATOrchestrator()
        
        if args.mode == 'status':
            # Solo mostrar estado
            estado = orchestrator.obtener_estado_servicios()
            print(json.dumps(estado, indent=2))
            return 0
        
        elif args.service:
            # Ejecutar servicio específico
            logger.info(f"Ejecutando servicio específico: {args.service}")
            exito, mensaje = orchestrator.ejecutar_servicio(args.service)
            if exito:
                logger.info(f"Servicio {args.service} ejecutado exitosamente")
                return 0
            else:
                logger.error(f"Servicio {args.service} falló: {mensaje}")
                return 1
        
        elif args.mode == 'full':
            # Pipeline completo
            resultados = orchestrator.ejecutar_pipeline_completo()
            return 0 if resultados['exitoso'] else 1
        
        elif args.mode == 'partial':
            # Pipeline parcial
            resultados = orchestrator.ejecutar_pipeline_parcial()
            return 0 if resultados['exitoso'] else 1
        
    except KeyboardInterrupt:
        logger.info("Ejecución interrumpida por usuario")
        return 1
    except Exception as e:
        logger.error(f"Error fatal: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
