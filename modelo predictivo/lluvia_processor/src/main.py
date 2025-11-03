#!/usr/bin/env python3
"""
SAT Pipeline - Lluvia Processor Service
Servicio para descarga y procesamiento de datos de lluvia del IDEAM
Basado en Lluvia_ideam_SAT_comp_1.ipynb
"""

import os
import sys
import logging
import pandas as pd
import geopandas as gpd
from datetime import datetime, timedelta
import requests
import json
from pathlib import Path
from shapely.geometry import Point

# librería para integración API Socrata (datos.gov.co)
from sodapy import Socrata

# Configuración de logging
def setup_logging():
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('/app/logs/lluvia_processor.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

class LluviaProcessor:
    def __init__(self):
        # Usar API de datos.gov.co como en el notebook
        self.app_token = os.getenv('IDEAM_TOKEN', 'VHmxDK45cRdGqCp2XBnesQVWQ')
        self.dataset_identifier = "s54a-sgyg"  # Dataset específico del notebook
        
        self.input_path = Path('/app/data/input')  # Archivos shapefile compartidos
        self.output_path = Path('/app/data/output/lluvia')  # Salida específica de lluvia
        
        # Archivos de entrada
        self.estaciones_path = self.input_path / 'estaciones_SAT_revis_nombres.shp'
        self.region_path = self.input_path / 'Region_andina_VivianaUrrea.shp'
        
        # Inicializar cliente Socrata
        self.client = Socrata("www.datos.gov.co", self.app_token, timeout=30)
        
        logger.info("LluviaProcessor inicializado con API Socrata")
        logger.info(f"Token: {self.app_token[:10]}...")
        logger.info(f"Dataset: {self.dataset_identifier}")
        logger.info(f"Ruta entrada: {self.input_path}")
        logger.info(f"Ruta salida: {self.output_path}")

    def verificar_archivos_entrada(self):
        """Verifica que existan los archivos necesarios"""
        archivos_requeridos = [
            self.estaciones_path,
            self.region_path
        ]
        
        for archivo in archivos_requeridos:
            if not archivo.exists():
                logger.error(f"Archivo requerido no encontrado: {archivo}")
                return False
        
        logger.info("Todos los archivos de entrada están disponibles")
        return True

    def cargar_estaciones(self):
        """Carga las estaciones desde el shapefile"""
        try:
            estaciones = gpd.read_file(self.estaciones_path)
            logger.info(f"Cargadas {len(estaciones)} estaciones")
            return estaciones
        except Exception as e:
            logger.error(f"Error cargando estaciones: {e}")
            raise

    def cargar_region(self):
        """Carga la región andina desde el shapefile"""
        try:
            region = gpd.read_file(self.region_path)
            logger.info(f"Región andina cargada con {len(region)} polígonos")
            return region
        except Exception as e:
            logger.error(f"Error cargando región: {e}")
            raise

    def obtener_datos_lluvia_masivos(self, fecha_inicio, fecha_fin):
        """Obtiene datos de lluvia masivos usando API Socrata (como en notebook)"""
        logger.info(f"Descargando datos desde {fecha_inicio} hasta {fecha_fin}...")
        
        # Inicializar variables para descarga por bloques
        all_data = []
        current_start = datetime.strptime(fecha_inicio, '%Y-%m-%dT%H:%M:%S')
        end_time = datetime.strptime(fecha_fin, '%Y-%m-%dT%H:%M:%S')
        block_size = 1  # días por bloque (optimizado para menor uso de RAM y mejor conectividad)
        max_retries = 3  # máximo 3 reintentos por bloque
        failed_blocks = []  # lista de bloques que fallaron completamente
        
        while current_start < end_time:
            current_end = min(current_start + timedelta(days=block_size), end_time)
            
            start_str = current_start.strftime("%Y-%m-%dT%H:%M:%S")
            end_str = current_end.strftime("%Y-%m-%dT%H:%M:%S")
            
            # Intentar descargar bloque con reintentos
            block_data = []
            retry_count = 0
            block_success = False
            
            while retry_count <= max_retries and not block_success:
                if retry_count > 0:
                    logger.info(f"Reintentando bloque desde {start_str} hasta {end_str} (intento {retry_count + 1}/{max_retries + 1})...")
                else:
                    logger.info(f"Descargando bloque desde {start_str} hasta {end_str}...")
                
                offset = 0
                limit = 2000
                block_data = []
                batch_errors = 0
                
                while True:
                    try:
                        batch = self.client.get(
                            dataset_identifier=self.dataset_identifier,
                            select="*",
                            where=f"fechaobservacion >= '{start_str}' AND fechaobservacion <= '{end_str}'",
                            limit=limit,
                            offset=offset
                        )
                        
                        if not batch:
                            break
                            
                        block_data.extend(batch)
                        offset += limit
                        logger.info(f"  Descargados {len(batch)} registros (bloque total: {len(block_data)})")
                        
                    except Exception as e:
                        batch_errors += 1
                        logger.error(f"Error al obtener datos entre {start_str} y {end_str}: {e}")
                        
                        # Intentar continuar con el siguiente batch en lugar de romper todo el bloque
                        if "timeout" in str(e).lower() or "connection" in str(e).lower():
                            logger.warning(f"Error de conectividad en batch {offset//limit + 1}, continuando...")
                            offset += limit
                            if batch_errors < 5:  # máximo 5 errores de batch por bloque
                                continue
                            else:
                                logger.warning(f"Demasiados errores de batch ({batch_errors}), terminando bloque...")
                                break
                        else:
                            logger.warning(f"Error no recuperable en bloque, terminando...")
                            break
                
                # Verificar si el bloque fue exitoso (obtuvo al menos algunos datos)
                if len(block_data) > 0:
                    block_success = True
                    all_data.extend(block_data)
                    logger.info(f"Bloque completado: {len(block_data)} registros")
                else:
                    retry_count += 1
                    if retry_count <= max_retries:
                        logger.warning(f"Bloque falló, reintentando en 5 segundos...")
                        import time
                        time.sleep(5)
            
            # Si después de todos los reintentos no se obtuvo nada, registrar el bloque fallido
            if not block_success:
                failed_blocks.append((start_str, end_str))
                logger.error(f"Bloque PERDIDO después de {max_retries + 1} intentos: {start_str} - {end_str}")
            
            current_start = current_end
        
        # Reporte final de descarga
        total_days = (end_time - datetime.strptime(fecha_inicio, '%Y-%m-%dT%H:%M:%S')).days + 1
        failed_days = len(failed_blocks) * block_size
        success_percentage = ((total_days - failed_days) / total_days) * 100
        
        logger.info(f"REPORTE DE DESCARGA:")
        logger.info(f"  Total registros descargados: {len(all_data)}")
        logger.info(f"  Días solicitados: {total_days}")
        logger.info(f"  Bloques fallidos: {len(failed_blocks)}")
        logger.info(f"  Días perdidos: {failed_days}")
        logger.info(f"  Cobertura exitosa: {success_percentage:.1f}%")
        
        if failed_blocks:
            logger.warning(f"  Bloques perdidos: {failed_blocks}")
        
        return all_data, success_percentage



    def filtrar_region_andina(self, df_nrt):
        """Filtra estaciones en la región andina (como en notebook) con optimización de memoria"""
        logger.info("Filtrando estaciones en región andina...")
        
        # Cargar región andina
        region_andina = self.cargar_region()
        
        # Confirmar sistema de referencia (como en notebook)
        region_andina = region_andina.to_crs(epsg=4326)
        
        # Asegurar que latitud y longitud sean numéricas
        df_nrt['latitud'] = pd.to_numeric(df_nrt['latitud'], errors='coerce')
        df_nrt['longitud'] = pd.to_numeric(df_nrt['longitud'], errors='coerce')
        
        # Filtrar registros con coordenadas válidas primero
        df_validas = df_nrt.dropna(subset=['latitud', 'longitud']).copy()
        logger.info(f"Registros con coordenadas válidas: {len(df_validas)}")
        
        # Procesamiento en chunks para reducir memoria
        chunk_size = 50000  # Procesar en chunks de 50k registros
        resultados_filtrados = []
        
        for i in range(0, len(df_validas), chunk_size):
            chunk = df_validas.iloc[i:i+chunk_size].copy()
            logger.info(f"Procesando chunk {i//chunk_size + 1}: {len(chunk)} registros")
            
            # Crear geometría de puntos para este chunk
            geometry = [Point(xy) for xy in zip(chunk['longitud'], chunk['latitud'])]
            
            # Crear GeoDataFrame del chunk
            gdf_chunk = gpd.GeoDataFrame(chunk, geometry=geometry, crs="EPSG:4326")
            
            # Filtrar estaciones dentro de región andina
            chunk_filtrado = gdf_chunk[gdf_chunk.within(region_andina.geometry.union_all())]
            
            if not chunk_filtrado.empty:
                resultados_filtrados.append(chunk_filtrado)
            
            # Liberar memoria del chunk
            del chunk, gdf_chunk, geometry
            import gc
            gc.collect()
        
        # Combinar todos los resultados
        if resultados_filtrados:
            gdf_nrt_andina = gpd.GeoDataFrame(pd.concat(resultados_filtrados, ignore_index=True))
            logger.info(f"Estaciones filtradas: {len(gdf_nrt_andina)} de {len(df_nrt)} originales")
        else:
            logger.warning("No se encontraron estaciones en la región andina")
            # Crear GeoDataFrame vacío con las mismas columnas
            gdf_nrt_andina = gpd.GeoDataFrame(columns=df_nrt.columns.tolist() + ['geometry'])
        
        return gdf_nrt_andina

    def procesar_datos_completos(self):
        """Procesa datos completos siguiendo lógica del notebook"""
        if not self.verificar_archivos_entrada():
            raise Exception("Archivos de entrada no disponibles")
        
        # Definir período de consulta (30 días completos)
        days_back = 30  # Período completo de 30 días
        end_time = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0)
        start_time = (end_time - timedelta(days=days_back)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        fecha_inicio_str = start_time.strftime('%Y-%m-%dT%H:%M:%S')
        fecha_fin_str = end_time.strftime('%Y-%m-%dT%H:%M:%S')
        
        logger.info(f"Procesando datos desde {fecha_inicio_str} hasta {fecha_fin_str}")
        
        # Intentar descarga con reintentos completos si cobertura es insuficiente
        max_complete_retries = 2  # máximo 2 reintentos completos
        min_coverage = 70.0  # Umbral reducido para permitir procesamiento con problemas de conectividad
        
        for attempt in range(max_complete_retries + 1):
            if attempt > 0:
                logger.warning(f"REINTENTO COMPLETO #{attempt} - Cobertura anterior insuficiente")
                import time
                time.sleep(10)  # esperar 10 segundos antes del reintento
            
            # Obtener datos masivos con reporte de cobertura
            all_data, success_percentage = self.obtener_datos_lluvia_masivos(fecha_inicio_str, fecha_fin_str)
            
            # Verificar cobertura mínima
            if success_percentage >= min_coverage:
                logger.info(f"Cobertura aceptable: {success_percentage:.1f}% - Continuando procesamiento...")
                
                # GUARDAR DATOS RAW INMEDIATAMENTE después de descarga exitosa
                logger.info("Guardando datos raw como respaldo...")
                try:
                    df_raw = pd.DataFrame.from_records(all_data)
                    fecha_max = pd.to_datetime(df_raw['fechaobservacion']).max()
                    fecha_max_str = fecha_max.strftime('%Y-%m-%d')
                    
                    raw_backup = self.output_path / f'RAW_lluvia_backup_{fecha_max_str}.csv.gz'
                    self.output_path.mkdir(parents=True, exist_ok=True)
                    df_raw.to_csv(raw_backup, compression='gzip', index=False)
                    logger.info(f"Respaldo guardado: {raw_backup}")
                except Exception as e:
                    logger.warning(f"No se pudo guardar respaldo: {e}")
                
                break
            else:
                logger.warning(f"Cobertura insuficiente: {success_percentage:.1f}% < {min_coverage}%")
                if attempt < max_complete_retries:
                    logger.info(f"Reintentando descarga completa (intento {attempt + 2}/{max_complete_retries + 1})...")
                else:
                    logger.warning(f"FALLO FINAL: Cobertura insuficiente después de {max_complete_retries + 1} intentos")
                    # Si tenemos al menos 50% de datos, continuar procesamiento
                    if success_percentage >= 50.0 and len(all_data) > 0:
                        logger.info(f"Procesando con cobertura reducida: {success_percentage:.1f}%")
                        
                        # Guardar respaldo de todos modos
                        logger.info("Guardando datos raw como respaldo...")
                        try:
                            df_raw = pd.DataFrame.from_records(all_data)
                            fecha_max = pd.to_datetime(df_raw['fechaobservacion']).max()
                            fecha_max_str = fecha_max.strftime('%Y-%m-%d')
                            
                            raw_backup = self.output_path / f'RAW_lluvia_backup_{fecha_max_str}.csv.gz'
                            self.output_path.mkdir(parents=True, exist_ok=True)
                            df_raw.to_csv(raw_backup, compression='gzip', index=False)
                            logger.info(f"Respaldo guardado: {raw_backup}")
                            del df_raw
                            import gc
                            gc.collect()
                        except Exception as e:
                            logger.warning(f"No se pudo guardar respaldo: {e}")
                        break
                    else:
                        logger.error("Datos insuficientes para procesamiento - Terminando proceso")
                        raise Exception(f"Cobertura de datos insuficiente: {success_percentage:.1f}% después de {max_complete_retries + 1} intentos")
        
        if not all_data:
            logger.error("No se obtuvieron datos de la API")
            raise Exception("Sin datos de API")
        
        # Convertir a DataFrame con optimización de memoria
        logger.info(f"Convirtiendo {len(all_data)} registros a DataFrame...")
        df_nrt = pd.DataFrame.from_records(all_data)
        logger.info(f"DataFrame creado con {len(df_nrt)} registros")
        
        # Liberar memoria del raw data inmediatamente
        del all_data
        import gc
        gc.collect()
        logger.info("Memoria raw data liberada")
        
        # Verificar fechas para ver si el periodo disponible es correcto
        # Verificación de fechas 
        df_nrt['fechaobservacion'] = pd.to_datetime(df_nrt['fechaobservacion'])
        
        # Imprimir fecha del periodo disponible
        logger.info(f"Rango de fechas: {df_nrt['fechaobservacion'].min()} a {df_nrt['fechaobservacion'].max()}")
        
        # Guardar fecha máxima para poner en la ruta de archivo cuando exporte
        fecha_max = df_nrt['fechaobservacion'].max()
        # Convertir a string sin la hora, en formato 'YYYY-MM-DD':
        fecha_max_str = fecha_max.strftime('%Y-%m-%d')
        
        # ARCHIVO INTERMEDIO DESHABILITADO - Solo guardamos resultado final exitoso
        # try:
        #     archivo_intermedio = self.output_path / f'Ideam_lluvia_30d_{fecha_max_str}.csv.gz'
        #     self.output_path.mkdir(parents=True, exist_ok=True)
        #     df_nrt.to_csv(archivo_intermedio, compression='gzip', index=False)
        #     logger.info(f"Archivo intermedio guardado: {archivo_intermedio}")
        # except Exception as e:
        #     logger.warning(f"No se pudo guardar archivo intermedio: {e}")
        
        logger.info("Continuando procesamiento...")
        
        # Filtrar por región andina con liberación de memoria
        logger.info("Filtrando por región andina...")
        gdf_nrt_andina = self.filtrar_region_andina(df_nrt)
        
        # Liberar DataFrame original
        del df_nrt
        gc.collect()
        logger.info("DataFrame original liberado después del filtro")
        
        # Procesar a lluvia diaria (como en notebook)
        logger.info("☔ Procesando a lluvia diaria...")
        df_lluvia_procesada = self.procesar_lluvia_diaria(gdf_nrt_andina)
        
        # Liberar GeoDataFrame
        del gdf_nrt_andina
        gc.collect()
        logger.info("🧹 GeoDataFrame liberado después del procesamiento")
        
        return df_lluvia_procesada

    def procesar_lluvia_diaria(self, gdf_nrt_andina):
        """Desde acá llevo los datos de lluvia de la región andina a lluvia diaria"""
        logger.info("Procesando lluvia diaria...")
        
        # Creo una copia del dataframe para no tener problemas
        gdf_nrt_andina2 = gdf_nrt_andina.copy()
        
        # Me aseguro que estén en el formato correcto (string sin espacios)
        gdf_nrt_andina2['codigoestacion'] = gdf_nrt_andina2['codigoestacion'].astype(str).str.strip()
        gdf_nrt_andina2['fechaobservacion'] = pd.to_datetime(gdf_nrt_andina2['fechaobservacion'], errors='coerce')
        gdf_nrt_andina2['valorobservado'] = pd.to_numeric(gdf_nrt_andina2['valorobservado'], errors='coerce')
        
        # Crear columna fecha para que sea la lluvia diaria (formato del modelo)
        gdf_nrt_andina2['fecha'] = gdf_nrt_andina2['fechaobservacion'].dt.date
        
        # Agrupo por estación y fecha los datos de lluvia en nuevo dataframe
        # Incluyo municipio y departamento para poder usarlo en nivel 2
        df_lluvia_diaria = (
            gdf_nrt_andina2
            .groupby(['codigoestacion', 'fecha', 'municipio', 'departamento'])['valorobservado']
            .sum()
            .reset_index(name='lluvia_diaria')
        )
        
        logger.info(f"Lluvia diaria procesada: {len(df_lluvia_diaria)} registros")
        
        # Aplicar control de calidad
        df_lluvia_filtrado = self.control_calidad_datos(df_lluvia_diaria)
        
        # Generar formato del modelo con acumulados
        df_final = self.generar_formato_modelo(df_lluvia_filtrado)
        
        # Validar información de lluvia antes de retornar
        self.validar_datos_lluvia(df_final)
        
        return df_final

    def validar_datos_lluvia(self, resultados_pivot):
        """Verificar que la información de lluvia sea correcta antes de exportar (como en notebook)"""
        logger.info("Validando información de lluvia...")
        
        # Seleccionar columnas de lluvia
        columnas_lluvia = resultados_pivot.columns[2:]  # desde la 3ra columna en adelante
        
        # Ver cuántos NaNs hay por columna
        nans_por_columna = resultados_pivot[columnas_lluvia].isna().sum()
        logger.info("NaNs por columna:")
        for col, nan_count in nans_por_columna.items():
            if nan_count > 0:
                logger.warning(f"  {col}: {nan_count} valores NaN")
            else:
                logger.info(f"  {col}: {nan_count} valores NaN")
        
        # Revisar tipos de datos por columna
        logger.info("Tipos de datos por columna:")
        for col in columnas_lluvia:
            dtype = resultados_pivot[col].dtypes
            logger.info(f"  {col}: {dtype}")
        
        # Verificar si hay valores no numéricos
        logger.info("Verificando valores no numéricos:")
        for col in columnas_lluvia:
            errores = pd.to_numeric(resultados_pivot[col], errors='coerce').isna().sum()
            if errores > 0:
                logger.warning(f"  {col}: {errores} valores no numéricos")
            else:
                logger.info(f"  {col}: {errores} valores no numéricos")
        
        # Estadísticas básicas
        logger.info("Estadísticas básicas de columnas de lluvia:")
        for col in columnas_lluvia:
            if col in resultados_pivot.columns:
                stats = resultados_pivot[col].describe()
                logger.info(f"  {col}: min={stats['min']:.2f}, max={stats['max']:.2f}, mean={stats['mean']:.2f}")
        
        logger.info("Validación de datos completada")

    def control_calidad_datos(self, df_lluvia_diaria):
        """
        Realizo control de calidad de los datos de lluvia:
        elimino estaciones que no alcanzan 80% de los datos y las que no tienen todos los últimos 4 días de registro
        """
        logger.info("Aplicando control de calidad...")
        
        # 1. Verificar estaciones con menos del 80% de los días con datos
        # Contar cuántos días hay por estación
        conteo_dias = df_lluvia_diaria.groupby('codigoestacion')['fecha'].nunique().reset_index()
        conteo_dias.columns = ['codigoestacion', 'num_dias']
        
        # Calcular el umbral dinámico basado en el período total de datos
        # Para período de 14 días: 80% = 11.2 días, redondeamos a 11 días mínimo
        total_dias_disponibles = df_lluvia_diaria['fecha'].nunique()
        umbral_minimo_dias = int(total_dias_disponibles * 0.8)  # 80% de cobertura
        
        logger.info(f"Período total: {total_dias_disponibles} días, umbral mínimo: {umbral_minimo_dias} días")
        
        # Filtrar estaciones con menos del 80% de días con datos
        estaciones_con_faltantes = conteo_dias[conteo_dias['num_dias'] < umbral_minimo_dias]
        
        dias_maximos_faltantes = total_dias_disponibles - umbral_minimo_dias
        logger.info(f"Total de estaciones con más de {dias_maximos_faltantes} días faltantes: {len(estaciones_con_faltantes)}")
        if len(estaciones_con_faltantes) > 0:
            logger.info("Estaciones con datos faltantes:")
            for idx, row in estaciones_con_faltantes.sort_values('num_dias').iterrows():
                dias_faltantes = total_dias_disponibles - row['num_dias']
                logger.info(f"  {row['codigoestacion']}: {row['num_dias']} días ({dias_faltantes} días faltantes)")
        
        # Obtener lista de estaciones con datos incompletos
        estaciones_a_excluir = estaciones_con_faltantes['codigoestacion'].unique()
        
        # Crear un nuevo DataFrame excluyendo esas estaciones
        df_lluvia_completo = df_lluvia_diaria[~df_lluvia_diaria['codigoestacion'].isin(estaciones_a_excluir)].copy()
        
        logger.info(f"Excluyendo {len(estaciones_a_excluir)} estaciones con datos incompletos")
        
        # 2. Filtrar las estaciones que no tienen los últimos 4 días de registro (que son necesarios en el modelo)
        # Asegurar que 'fecha' sea datetime64[ns]
        df_lluvia_completo['fecha'] = pd.to_datetime(df_lluvia_completo['fecha'])
        
        # Verificar que tengamos datos después de las exclusiones
        if df_lluvia_completo.empty:
            logger.error("No quedan datos después de las exclusiones de calidad")
            raise Exception("Sin datos después de control de calidad")
        
        # Se define la fecha más reciente de registro
        fecha_final = df_lluvia_completo['fecha'].max()
        
        # Verificar que fecha_final no sea NaT
        if pd.isna(fecha_final):
            logger.error("Fecha final es NaT - datos de fecha inválidos")
            raise Exception("Fecha final inválida")
        
        logger.info(f"Fecha final de datos: {fecha_final}")
        
        # Genera los últimos 4 días desde la fecha más reciente
        ultimos_dias = pd.date_range(end=fecha_final, periods=4)
        
        # Filtrar el DataFrame solo con los últimos 4 días
        df_ultimos4 = df_lluvia_completo[df_lluvia_completo['fecha'].isin(ultimos_dias)]
        
        # Contar cuántos días tiene cada estación en ese rango
        conteo_por_estacion = df_ultimos4.groupby('codigoestacion')['fecha'].nunique()
        
        # Detectar estaciones que tienen menos de 4 días
        estaciones_incompletas = conteo_por_estacion[conteo_por_estacion < 4].index.tolist()
        
        logger.info(f"Número de estaciones con datos faltantes en los últimos 4 días: {len(estaciones_incompletas)}")
        
        # Filtro estaciones que no tienen últimos 4 días de datos
        df_lluvia_filtrado = df_lluvia_completo[~df_lluvia_completo['codigoestacion'].isin(estaciones_incompletas)]
        
        # 3. Revisar y tratar inconsistencias en las estaciones
        logger.info("Revisando inconsistencias en municipios y departamentos...")
        
        inconsistencias = df_lluvia_filtrado.groupby('codigoestacion')[['municipio', 'departamento']].nunique()
        inconsistencias = inconsistencias[(inconsistencias['municipio'] > 1) | (inconsistencias['departamento'] > 1)]
        
        # Lista estaciones con inconsistencias 
        codigos_inconsistentes = inconsistencias.index.tolist()
        
        if len(codigos_inconsistentes) > 0:
            logger.info(f"Encontradas {len(codigos_inconsistentes)} estaciones con inconsistencias:")
            logger.info(f"Inconsistencias:\n{inconsistencias}")
            
            # REVISAR Y CORREGIR INCONSISTENCIAS de mpios o deptos con un shape de estaciones
            df_lluvia_filtrado = self.corregir_inconsistencias_localidades(df_lluvia_filtrado, codigos_inconsistentes)
        
        logger.info(f"Control de calidad completado: {len(df_lluvia_filtrado)} registros finales")
        
        return df_lluvia_filtrado

    def corregir_inconsistencias_localidades(self, df_lluvia_filtrado, codigos_inconsistentes):
        """Corrige inconsistencias de municipios/departamentos usando shapefile de estaciones"""
        try:
            # Leer shape de estaciones
            if self.estaciones_path.exists():
                shape_estaciones = gpd.read_file(self.estaciones_path)
                
                # Establecer formato correcto para comparación (string sin espacios)
                shape_estaciones['codigo'] = shape_estaciones['codigo'].astype(str).str.strip()
                
                # Crear diccionarios con mpios definidos en el shapefile
                dict_mpio_def = shape_estaciones.set_index('codigo')['mpio_def'].to_dict()
                dict_depto_def = shape_estaciones.set_index('codigo')['depto_def'].to_dict()
                
                # Reemplazar en el dataframe original solo si hay inconsistencias
                df_lluvia_filtrado.loc[df_lluvia_filtrado['codigoestacion'].isin(codigos_inconsistentes), 'municipio'] = \
                    df_lluvia_filtrado['codigoestacion'].map(dict_mpio_def)
                
                df_lluvia_filtrado.loc[df_lluvia_filtrado['codigoestacion'].isin(codigos_inconsistentes), 'departamento'] = \
                    df_lluvia_filtrado['codigoestacion'].map(dict_depto_def)
                
                logger.info("Inconsistencias corregidas usando shapefile de estaciones")
            else:
                logger.warning("Shapefile de estaciones no encontrado, no se pueden corregir inconsistencias")
                
        except Exception as e:
            logger.error(f"Error corrigiendo inconsistencias: {e}")
        
        return df_lluvia_filtrado

    def generar_formato_modelo(self, df_lluvia_filtrado):
        """Genera formato del modelo con acumulados (como en notebook)"""
        logger.info("Generando formato del modelo con acumulados de lluvia...")
        
        # Verificar que tengamos datos
        if df_lluvia_filtrado.empty:
            logger.error("No hay datos filtrados para generar formato del modelo")
            raise Exception("Sin datos para modelo")
        
        # mod: Para generar lluvia acumulada en formato de modelo con MUNICIPIOS
        # Identificar fecha máxima en el df
        fecha_final = df_lluvia_filtrado['fecha'].max()
        
        # Verificar que fecha_final no sea NaT
        if pd.isna(fecha_final):
            logger.error("Fecha final es NaT en formato del modelo")
            raise Exception("Fecha final inválida en modelo")
        
        logger.info(f"Fecha final para modelo: {fecha_final}")
        
        # Ventanas deseadas de días para formato del modelo
        ventanas = [1, 2, 3, 15, 30]
        
        # Lista para guardar resultados
        resultados = []
        
        # Iterar por estación y calcular acumulados por cada ventana
        for estacion, grupo in df_lluvia_filtrado.groupby('codigoestacion'):
            # Filtramos los últimos 30 días para esta estación
            datos_est = grupo[grupo['fecha'] >= (fecha_final - pd.Timedelta(days=29))].copy()
            
            # Ordenar en forma descendente (día 0 primero, el más reciente)
            datos_est = datos_est.sort_values('fecha', ascending=False).reset_index(drop=True)
            
            if datos_est.empty:
                continue
                
            # Obtener municipio y departamento
            mpio = datos_est.loc[0, 'municipio']
            depto = datos_est.loc[0, 'departamento']
            
            # Registrar el día 0 (más reciente)
            if not datos_est.empty:
                lluvia_dia_0 = datos_est.loc[0, 'lluvia_diaria']
                fecha_dia_0 = datos_est.loc[0, 'fecha']
                # Agregar a los resultados
                resultados.append({
                    'codigoestacion': estacion,
                    'dias_acumulados': 0,
                    'lluvia_acumulada': lluvia_dia_0,
                    'fecha': fecha_dia_0,
                    'municipio': mpio,
                    'departamento': depto
                })
            
            # Excluir el día 0 para los acumulados
            datos_sin_dia0 = datos_est.iloc[1:]
            
            # Calcular acumulados desde el día 1-ant
            for dias in ventanas:
                acumulado = datos_sin_dia0.head(dias)['lluvia_diaria'].sum()
                # Agregar columna "Fecha" con la fecha de corte o la última disponible en el caso del día 30
                if dias < len(datos_est):
                    fecha_corte = datos_est.loc[dias, 'fecha']
                else:
                    fecha_corte = datos_est['fecha'].iloc[-1]  # Última fecha disponible
                
                # Agregar a los resultados
                resultados.append({
                    'codigoestacion': estacion,
                    'dias_acumulados': dias,
                    'lluvia_acumulada': acumulado,
                    'fecha': fecha_corte,
                    'municipio': mpio,
                    'departamento': depto,
                })
        
        # Crear DataFrame final
        df_acumulados = pd.DataFrame(resultados)
        
        # Pivotear resultados para dejar solo una fila por estacion (formato del modelo)
        # Renombrar lluvia del día 0 para que tenga el nombre especial de daily rain
        df_acumulados['nombre_columna'] = df_acumulados['dias_acumulados'].apply(
            lambda x: 'daily rain' if x == 0 else f'{x}-rain ant.rain'
        )
        
        # Luego, pivotea
        resultados_pivot = df_acumulados.pivot(
            index='codigoestacion', 
            columns='nombre_columna', 
            values='lluvia_acumulada'
        )
        
        # Extraer la fecha del día 0 para tener una columna de fecha
        fecha_daily = df_acumulados[df_acumulados['dias_acumulados'] == 0][['codigoestacion', 'fecha']]
        fecha_daily = fecha_daily.rename(columns={'fecha': 'data'})
        
        # Resetear índice para que 'codigoestacion' sea una columna normal
        resultados_pivot = resultados_pivot.reset_index()
        
        # Combinar resultados del pivote y la fecha del día 0
        resultados_pivot = resultados_pivot.merge(fecha_daily, on='codigoestacion', how='left')
        
        # Asignar un orden a las columnas según el modelo
        orden_columnas = ['codigoestacion', 'data', 'daily rain', '1-rain ant.rain', '2-rain ant.rain',
                          '3-rain ant.rain', '15-rain ant.rain', '30-rain ant.rain']
        
        resultados_pivot = resultados_pivot[orden_columnas]
        
        logger.info(f"Formato del modelo generado: {len(resultados_pivot)} estaciones")
        
        return resultados_pivot

    def guardar_resultados(self, df_resultados):
        """
        Exportar dataframe de lluvia diaria nivel 1
        Para usarlo en el notebook del modelo (Modelo_SAT)
        """
        try:
            # Crear directorio de salida si no existe
            self.output_path.mkdir(parents=True, exist_ok=True)
            
            # Previo a exportar dataframe, guardar fecha para incluir en la ruta de archivo
            # Obtener la fecha de daily rain del df resultados
            fecha_df = df_resultados['data'].iloc[0]
            
            # Convertir fecha a str para usarla en el archivo para guardar
            if isinstance(fecha_df, str):
                fecha_str = pd.to_datetime(fecha_df).strftime('%Y-%m-%d')
            else:
                fecha_str = fecha_df.strftime('%Y-%m-%d')
            
            # Construir la ruta completa del archivo
            archivo_salida = self.output_path / f'lluvia_30d_{fecha_str}.csv'
            
            # Exportar dataframe para formato de modelo 
            df_resultados.to_csv(archivo_salida, index=False, encoding='utf-8-sig')
            logger.info(f"Resultados guardados en: {archivo_salida}")
            
            # También guardar con nombre fijo para uso posterior (latest)
            archivo_ultimo = self.output_path / 'lluvia_procesada_latest.csv'
            df_resultados.to_csv(archivo_ultimo, index=False, encoding='utf-8-sig')
            logger.info(f"Último resultado en: {archivo_ultimo}")
            
            # Crear resumen JSON
            columnas_lluvia = [col for col in df_resultados.columns if 'rain' in col]
            
            resumen = {
                'fecha_datos': fecha_str,
                'timestamp_proceso': datetime.now().strftime('%Y%m%d_%H%M%S'),
                'total_estaciones': len(df_resultados),
                'estaciones_con_datos': len(df_resultados[df_resultados['daily rain'] > 0]),
                'columnas_lluvia': columnas_lluvia,
                'estadisticas': {
                    col: {
                        'promedio': float(df_resultados[col].mean()),
                        'maximo': float(df_resultados[col].max()),
                        'minimo': float(df_resultados[col].min())
                    } for col in columnas_lluvia
                },
                'archivo_datos': str(archivo_ultimo)
            }
            
            archivo_resumen = self.output_path / 'resumen_lluvia.json'
            with open(archivo_resumen, 'w', encoding='utf-8') as f:
                json.dump(resumen, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Resumen guardado en: {archivo_resumen}")
            
            return archivo_ultimo, archivo_resumen
            
        except Exception as e:
            logger.error(f"Error guardando resultados: {e}")
            raise

def main():
    """Función principal del servicio"""
    logger.info("=== Iniciando SAT Lluvia Processor (versión notebook) ===")
    
    try:
        # Inicializar procesador
        processor = LluviaProcessor()
        
        # Procesar datos completos (siguiendo lógica del notebook)
        logger.info("Iniciando procesamiento completo...")
        df_resultados = processor.procesar_datos_completos()
        
        # Guardar resultados
        logger.info("Guardando resultados...")
        archivo_datos, archivo_resumen = processor.guardar_resultados(df_resultados)
        
        logger.info("=== Procesamiento completado exitosamente ===")
        logger.info(f"Datos disponibles en: {archivo_datos}")
        logger.info(f"Resumen en: {archivo_resumen}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error fatal en procesamiento: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
