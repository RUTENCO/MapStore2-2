#!/usr/bin/env python3
"""
SAT Pipeline - Modelo SAT Service
Servicio para ejecutar el modelo de predicción de deslizamientos
Basado en Modelo_SAT_comp_2.ipynb

NOTA: Por la versión del scikit learn del modelo, este debe correrse en Python 3.9.21
Nombre del entorno: ambiente_SAT
"""

import os
import sys
import logging
import pandas as pd
import numpy as np
import geopandas as gpd
from datetime import datetime
import pickle
import json
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import joblib
import gdown
import requests

# Configuración de logging
def setup_logging():
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('/app/logs/modelo_sat.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

class ModeloSAT:
    def __init__(self):
        self.input_path = Path('/app/data/output/lluvia')  # Lee salida del lluvia_processor
        self.output_path = Path('/app/data/output/modelo')  # Salida específica del modelo
        self.models_path = Path('/app/models')
        self.data_path = Path('/app/data/input')  # Archivos shapefile compartidos
        
        # Archivos esperados
        self.estaciones_path = self.data_path / 'estaciones_SAT_revis_nombres.shp'
        
        # URL del modelo pre-entrenado (si no existe localmente)
        self.model_url = os.getenv('MODEL_URL', '')
        
        logger.info("ModeloSAT inicializado")
        logger.info(f"Ruta entrada: {self.input_path}")
        logger.info(f"Ruta salida: {self.output_path}")
        logger.info(f"Ruta modelos: {self.models_path}")

    def verificar_archivos_entrada(self):
        """Verifica que existan los archivos necesarios"""
        # Buscar archivo de lluvia más reciente (formato del notebook lluvia_ideam_SAT)
        archivos_lluvia = list(self.input_path.glob('lluvia_30d_*.csv'))
        archivo_latest = self.input_path / 'lluvia_procesada_latest.csv'
        
        if archivo_latest.exists():
            self.archivo_lluvia = archivo_latest
        elif archivos_lluvia:
            # Tomar el más reciente
            self.archivo_lluvia = max(archivos_lluvia, key=lambda x: x.stat().st_mtime)
        else:
            logger.error("No se encontró archivo de datos de lluvia")
            return False
        
        # Verificar estaciones
        if not self.estaciones_path.exists():
            logger.error(f"Archivo de estaciones no encontrado: {self.estaciones_path}")
            return False
        
        logger.info(f"Archivo de lluvia: {self.archivo_lluvia}")
        logger.info("Todos los archivos de entrada están disponibles")
        return True

    def cargar_datos_lluvia(self):
        """Carga los datos de lluvia procesados"""
        try:
            df_lluvia = pd.read_csv(self.archivo_lluvia)
            logger.info(f"Cargados datos de lluvia: {len(df_lluvia)} estaciones")
            
            # Verificar columnas necesarias (del formato del notebook lluvia_ideam_SAT)
            columnas_requeridas = ['codigoestacion', 'data', 'daily rain', '1-rain ant.rain', 
                                 '2-rain ant.rain', '3-rain ant.rain', '15-rain ant.rain', '30-rain ant.rain']
            columnas_faltantes = [col for col in columnas_requeridas if col not in df_lluvia.columns]
            
            if columnas_faltantes:
                logger.error(f"Columnas faltantes en datos de lluvia: {columnas_faltantes}")
                logger.info(f"Columnas disponibles: {list(df_lluvia.columns)}")
                raise ValueError(f"Columnas faltantes: {columnas_faltantes}")
            
            return df_lluvia
            
        except Exception as e:
            logger.error(f"Error cargando datos de lluvia: {e}")
            raise

    def cargar_estaciones(self):
        """Carga información adicional de estaciones"""
        try:
            estaciones = gpd.read_file(self.estaciones_path)
            logger.info(f"Cargadas {len(estaciones)} estaciones desde shapefile")
            return estaciones
        except Exception as e:
            logger.error(f"Error cargando estaciones: {e}")
            raise

    def descargar_modelo(self):
        """Descarga el modelo desde Google Drive si no existe localmente"""
        modelo_path = self.models_path / 'finalized_model_RF_andina_ideam.sav'  # Nombre exacto del notebook
        
        if modelo_path.exists():
            logger.info(f"Modelo encontrado localmente: {modelo_path}")
            return modelo_path
        
        try:
            logger.info("Descargando modelo desde Google Drive...")
            self.models_path.mkdir(parents=True, exist_ok=True)
            
            # ID del modelo en Google Drive (del notebook)
            file_id = "1gSDPM7g25Gn_Ql6vUCl0XMhmyUzCdMJ5"
            url = f"https://drive.google.com/uc?export=download&id={file_id}"
            gdown.download(url, str(modelo_path), quiet=False)
            
            logger.info(f"Modelo descargado exitosamente: {modelo_path}")
            return modelo_path
            
        except Exception as e:
            logger.error(f"Error descargando modelo desde Google Drive: {e}")
            logger.warning("No se pudo descargar el modelo pre-entrenado, usando modelo básico")
            return None

    def crear_modelo_basico(self):
        """Crea un modelo básico si no hay uno pre-entrenado"""
        logger.info("Creando modelo básico Random Forest")
        
        # Modelo básico con parámetros conservadores
        modelo = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42
        )
        
        return modelo

    def cargar_modelo(self):
        """Carga el modelo de ML"""
        try:
            modelo_path = self.descargar_modelo()
            
            if modelo_path and modelo_path.exists():
                # Intentar cargar con joblib primero
                try:
                    modelo = joblib.load(modelo_path)
                    logger.info("Modelo cargado exitosamente con joblib")
                    return modelo, True  # True indica que es un modelo pre-entrenado
                except:
                    # Intentar con pickle
                    try:
                        with open(modelo_path, 'rb') as f:
                            modelo = pickle.load(f)
                        logger.info("Modelo cargado exitosamente con pickle")
                        return modelo, True
                    except Exception as e:
                        logger.error(f"Error cargando modelo: {e}")
            
            # Si no se puede cargar, crear modelo básico
            modelo = self.crear_modelo_basico()
            return modelo, False  # False indica que es un modelo básico
            
        except Exception as e:
            logger.error(f"Error en carga de modelo: {e}")
            modelo = self.crear_modelo_basico()
            return modelo, False

    def preparar_features(self, df_lluvia):
        """Prepara las características para el modelo - exacto al notebook"""
        try:
            # Variables específicas del notebook Modelo_SAT_comp_2.ipynb
            variables = ['daily rain', '1-rain ant.rain',
                        '3-rain ant.rain', '15-rain ant.rain',
                        '30-rain ant.rain']
            
            # Verificar que existan las columnas necesarias
            columnas_faltantes = [col for col in variables if col not in df_lluvia.columns]
            if columnas_faltantes:
                logger.error(f"Columnas faltantes para modelo: {columnas_faltantes}")
                raise ValueError(f"Columnas faltantes: {columnas_faltantes}")
            
            # Filtrar dataframe para variables del modelo
            features = df_lluvia[variables].copy()
            
            # Rellenar NaN con 0 antes de estandarizar
            features = features.fillna(0)
            
            # Reemplazar infinitos
            features = features.replace([np.inf, -np.inf], 0)
            
            logger.info(f"Features preparadas: {features.shape}")
            logger.info(f"Columnas: {list(features.columns)}")
            
            return features
            
        except Exception as e:
            logger.error(f"Error preparando features: {e}")
            raise

    def calcular_probabilidades_basicas(self, features):
        """Calcula probabilidades usando reglas heurísticas básicas"""
        logger.info("Calculando probabilidades con reglas heurísticas")
        
        probabilidades = np.zeros(len(features))
        
        for i, row in features.iterrows():
            daily_rain = row['daily rain']
            rain_1d = row['1-rain ant.rain']
            rain_3d = row['3-rain ant.rain']
            rain_15d = row['15-rain ant.rain']
            rain_30d = row['30-rain ant.rain']
            
            # Reglas heurísticas basadas en umbrales de lluvia
            prob = 0.0
            
            # Lluvia intensa diaria
            if daily_rain > 50:
                prob += 0.3
            elif daily_rain > 30:
                prob += 0.2
            elif daily_rain > 15:
                prob += 0.1
            
            # Lluvia acumulada 3 días
            if rain_3d > 100:
                prob += 0.2
            elif rain_3d > 50:
                prob += 0.1
            
            # Lluvia acumulada 15 días
            if rain_15d > 200:
                prob += 0.2
            elif rain_15d > 100:
                prob += 0.1
            
            # Lluvia acumulada 30 días
            if rain_30d > 400:
                prob += 0.2
            elif rain_30d > 200:
                prob += 0.1
            
            # Limitar probabilidad entre 0 y 1
            probabilidades[i] = min(prob, 1.0)
        
        return probabilidades

    def ejecutar_prediccion(self, df_lluvia):
        """Ejecuta la predicción del modelo"""
        try:
            # Cargar modelo
            modelo, es_preentrenado = self.cargar_modelo()
            
            # Preparar features
            features = self.preparar_features(df_lluvia)
            
            if es_preentrenado:
                try:
                    # Intentar predicción con modelo pre-entrenado
                    probabilidades = modelo.predict_proba(features)[:, 1]  # Probabilidad de clase positiva
                    logger.info("Predicción ejecutada con modelo pre-entrenado")
                except Exception as e:
                    logger.warning(f"Error con modelo pre-entrenado, usando reglas heurísticas: {e}")
                    probabilidades = self.calcular_probabilidades_basicas(features)
            else:
                # Usar reglas heurísticas
                probabilidades = self.calcular_probabilidades_basicas(features)
            
            return probabilidades
            
        except Exception as e:
            logger.error(f"Error en predicción: {e}")
            # Fallback a probabilidades básicas
            features = self.preparar_features(df_lluvia)
            return self.calcular_probabilidades_basicas(features)

    def run_model(self, df_lluvia_features):
        """Función para correr el modelo con datos estandarizados - exacto al notebook"""
        try:
            # Estandarizar los datos de lluvia (como en el notebook)
            sc = StandardScaler()
            estandar = sc.fit_transform(df_lluvia_features)
            
            # Cargar modelo
            modelo, es_preentrenado = self.cargar_modelo()
            
            if es_preentrenado:
                # Correr el modelo (como en el notebook)
                probabilidad = modelo.predict_proba(estandar)  # Seguridad del modelo en cada clase
                prob_deslizamiento = probabilidad[:, 1]  # Clase con probabilidad de deslizamiento
                logger.info("Modelo ejecutado con StandardScaler y predict_proba")
                return prob_deslizamiento
            else:
                logger.warning("Usando modelo básico sin StandardScaler")
                return self.calcular_probabilidades_basicas(df_lluvia_features)
                
        except Exception as e:
            logger.error(f"Error en run_model: {e}")
            return self.calcular_probabilidades_basicas(df_lluvia_features)

    def clasificar_riesgo(self, probabilidad):
        """Clasifica el nivel de riesgo basado en la probabilidad"""
        if probabilidad >= 0.7:
            return "ALTO", "#FF0000"  # Rojo
        elif probabilidad >= 0.5:
            return "MEDIO-ALTO", "#FF8C00"  # Naranja
        elif probabilidad >= 0.3:
            return "MEDIO", "#FFD700"  # Amarillo
        elif probabilidad >= 0.1:
            return "BAJO-MEDIO", "#90EE90"  # Verde claro
        else:
            return "BAJO", "#00FF00"  # Verde

    def generar_resultados(self, df_lluvia, probabilidades):
        """Genera el dataset final con resultados"""
        try:
            # Crear DataFrame de resultados
            resultados = df_lluvia.copy()
            resultados['prob_ep'] = probabilidades  # Nombre exacto del notebook
            
            # Clasificar riesgo
            riesgo_info = [self.clasificar_riesgo(p) for p in probabilidades]
            resultados['nivel_riesgo'] = [info[0] for info in riesgo_info]
            resultados['color_riesgo'] = [info[1] for info in riesgo_info]
            
            # Agregar timestamp
            resultados['timestamp_prediccion'] = datetime.now().isoformat()
            
            # Ordenar por probabilidad descendente
            resultados = resultados.sort_values('prob_ep', ascending=False)
            
            logger.info(f"Resultados generados para {len(resultados)} estaciones")
            
            # Estadísticas
            stats = {
                'total_estaciones': len(resultados),
                'riesgo_alto': len(resultados[resultados['nivel_riesgo'] == 'ALTO']),
                'riesgo_medio_alto': len(resultados[resultados['nivel_riesgo'] == 'MEDIO-ALTO']),
                'riesgo_medio': len(resultados[resultados['nivel_riesgo'] == 'MEDIO']),
                'probabilidad_promedio': float(resultados['prob_ep'].mean()),
                'probabilidad_maxima': float(resultados['prob_ep'].max())
            }
            
            logger.info(f"Estadísticas de riesgo: {stats}")
            
            return resultados, stats
            
        except Exception as e:
            logger.error(f"Error generando resultados: {e}")
            raise

    def guardar_resultados(self, resultados, stats):
        """Guarda los resultados del modelo"""
        try:
            # Crear directorio de salida
            self.output_path.mkdir(parents=True, exist_ok=True)
            
            # Timestamp para archivos
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Guardar CSV con resultados completos
            archivo_csv = self.output_path / f'predicciones_sat_{timestamp}.csv'
            resultados.to_csv(archivo_csv, index=False)
            logger.info(f"Resultados CSV guardados: {archivo_csv}")
            
            # Archivo latest para uso posterior
            archivo_latest = self.output_path / 'predicciones_sat_latest.csv'
            resultados.to_csv(archivo_latest, index=False)
            
            # Crear GeoPackage para el siguiente paso (si hay información geográfica)
            try:
                # El shapefile de estaciones ya tiene geometría, usar esa
                if 'geometry' in resultados.columns:
                    gdf = gpd.GeoDataFrame(resultados, crs='EPSG:4326')
                else:
                    logger.warning("No hay información geográfica disponible, guardando solo CSV")
                    gdf = None
                
                if gdf is not None:
                    archivo_gpkg = self.output_path / f'predicciones_sat_{timestamp}.gpkg'
                    gdf.to_file(archivo_gpkg, driver='GPKG')
                    logger.info(f"GeoPackage guardado: {archivo_gpkg}")
                    
                    # Latest para siguiente etapa
                    archivo_gpkg_latest = self.output_path / 'predicciones_sat_latest.gpkg'
                    gdf.to_file(archivo_gpkg_latest, driver='GPKG')
                
            except Exception as e:
                logger.warning(f"No se pudo crear GeoPackage: {e}")
            
            # Guardar estadísticas
            stats_completas = {
                'timestamp': timestamp,
                'archivo_datos': str(archivo_latest),
                **stats
            }
            
            archivo_stats = self.output_path / 'estadisticas_modelo.json'
            with open(archivo_stats, 'w', encoding='utf-8') as f:
                json.dump(stats_completas, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Estadísticas guardadas: {archivo_stats}")
            
            return archivo_latest, archivo_stats
            
        except Exception as e:
            logger.error(f"Error guardando resultados: {e}")
            raise

    def str_convert(self, df):
        """Función convertir a string los códigos para consistencia del merge - del notebook"""
        df['codigo'] = df['codigo'].astype(str)
        return df

    def merge_resultados(self, estaciones, df_lluvia_prob):
        """Función merge resultados probabilidades de deslizamiento por estación - del notebook"""
        df_rtado = pd.merge(estaciones, df_lluvia_prob, how="left", left_on=['codigo'], right_on=['codigo'])
        # Eliminar filas con NaNs
        df_rtado = df_rtado.dropna(subset=['prob_ep'])
        return df_rtado

    def procesar(self):
        """Método principal siguiendo la lógica exacta del notebook"""
        logger.info("=== Iniciando procesamiento modelo SAT (siguiendo notebook) ===")
        
        try:
            # Verificar archivos de entrada
            if not self.verificar_archivos_entrada():
                logger.error("Archivos de entrada no disponibles")
                return False
            
            # Descargar modelo si es necesario
            modelo_path = self.descargar_modelo()
            
            # Cargar datos de lluvia
            logger.info("Cargando archivo IDEAM...")
            df_ideam = pd.read_csv(self.archivo_lluvia)
            
            # Renombrar columnas para el modelo (como en el notebook)
            df_ideam = df_ideam.rename(columns={
                'codigoestacion': 'codigo',
                'data': 'data',
                'daily rain': 'daily rain'
            })
            
            # Seleccionar variables necesarias para el modelo
            variables = ['daily rain', '1-rain ant.rain',
                        '3-rain ant.rain', '15-rain ant.rain',
                        '30-rain ant.rain']
            
            logger.info(f"Filtrando variables del modelo: {variables}")
            df_ideam2 = df_ideam[variables].copy()
            
            # CORRER modelo - resultado de probabilidades de deslizamiento
            logger.info("Ejecutando modelo de predicción...")
            rtado_probab = self.run_model(df_ideam2)
            
            # Agregar probabilidad deslizamiento al df de lluvia
            df_ideam['prob_ep'] = rtado_probab
            
            # Cargar estaciones shapefile
            logger.info("Cargando estaciones...")
            estaciones_lluvia = gpd.read_file(self.estaciones_path)
            
            # Convertir a string los códigos para hacer merge
            estaciones_lluvia = self.str_convert(estaciones_lluvia)
            df_ideam = self.str_convert(df_ideam)
            
            # Resultado probabilidades de deslizamiento NIVEL 1
            logger.info("Haciendo merge de resultados...")
            df_prob_ideam = self.merge_resultados(estaciones_lluvia, df_ideam)
            
            # Exportar geodataframe para generar GEOTIFF
            logger.info("Exportando resultados...")
            output_path = Path('/app/data/output/modelo')
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Exportar archivo GPKG que necesita geotiff_exporter
            archivo_gpkg = output_path / 'prob_deslizamientos.gpkg'
            df_prob_ideam.to_file(archivo_gpkg, driver="GPKG")
            logger.info(f"Archivo GPKG exportado: {archivo_gpkg} (para geotiff_exporter)")
            
            # Exportar CSV para análisis y compatibilidad
            archivo_csv = output_path / 'prob_deslizamientos.csv'
            df_prob_ideam.to_csv(archivo_csv, index=False)
            logger.info(f"Archivo CSV exportado: {archivo_csv} (para análisis)")
            
            # Estadísticas del procesamiento
            total_estaciones = len(df_prob_ideam)
            prob_promedio = df_prob_ideam['prob_ep'].mean()
            logger.info(f"Procesadas {total_estaciones} estaciones - Probabilidad promedio: {prob_promedio:.4f}")
            
            logger.info("=== Procesamiento modelo SAT completado exitosamente ===")
            return True
            
        except Exception as e:
            logger.error(f"Error en procesamiento: {e}")
            return False

def main():
    """Función principal del servicio"""
    logger.info("=== Iniciando SAT Modelo Predicción ===")
    
    try:
        # Inicializar modelo
        modelo_sat = ModeloSAT()
        
        # Procesar usando lógica del notebook
        if modelo_sat.procesar():
            logger.info("Procesamiento exitoso")
            return 0
        else:
            logger.error("Error en procesamiento")
            return 1
        
    except Exception as e:
        logger.error(f"Error fatal en predicción: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
