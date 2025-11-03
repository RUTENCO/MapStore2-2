#!/usr/bin/env python3
"""
SAT Pipeline - GeoTIFF Exporter Service
Implementación exacta del notebook Gtiff_export_3.ipynb
"""

import os
import sys
import logging
import numpy as np
from scipy.interpolate import griddata
from rasterio.transform import from_origin
import pandas
import geopandas as gpd
import matplotlib.pyplot as plt
import rasterio
from pathlib import Path
from datetime import datetime

# Configuración de logging
def setup_logging():
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('/app/logs/geotiff_exporter.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

class GeoTIFFExporter:
    def __init__(self):
        self.input_path = Path('/app/data/output/modelo')  # Lee salida del modelo_sat
        self.output_path = Path('/app/data/output/geotiff')  # Salida específica de geotiff

        logger.info("GeoTIFFExporter inicializado")
        logger.info(f"Ruta entrada: {self.input_path}")
        logger.info(f"Ruta salida: {self.output_path}")

    def interpolate_geotiff(self, gdf_points, value_col, out_tif,
                            target_crs="EPSG:3116",
                            pixel_size=1000,
                            method='linear',   # 'linear'|'nearest'|'cubic'|'idw'
                            idw_power=2,
                            nodata=np.nan,
                            dtype='float32'):
        """
        Interpola puntos sobre una rejilla regular (en CRS métrico) y guarda GeoTIFF.
        Implementación exacta del notebook Gtiff_export_3.ipynb
        - gdf_points: GeoDataFrame con geometría puntual y crs definido.
        - value_col: columna con valores a interpolar (ej 'prob_ep').
        - out_tif: ruta salida .tif
        - target_crs: reproyecta internamente los puntos (usar proj. en metros, ej 'EPSG:3116').
        - pixel_size: tamaño de píxel en unidades del CRS objetivo (metros si EPSG:3116).
        - method: 'linear','nearest','cubic' (griddata) o 'idw' para IDW simple.
        - idw_power: exponente para IDW (si method=='idw').
        - nodata: valor no-datos en el tif.
        - dtype: tipo de dato para el GeoTIFF.
        """
        # 0. chequeos
        if gdf_points.empty:
            raise ValueError("gdf_points está vacío")
        if value_col not in gdf_points.columns:
            raise ValueError(f"{value_col} no existe en gdf_points")

        # 1. reproyectar a CRS objetivo (métrico)
        g = gdf_points.to_crs(target_crs)

        # 2. obtener coordenadas y valores
        xs = g.geometry.x.values
        ys = g.geometry.y.values
        vals = g[value_col].values.astype(float)

        # 3. bounds y rejilla (centros de píxel)
        minx, miny, maxx, maxy = g.total_bounds
        # crear coordenadas de centros de celda
        x_coords = np.arange(minx + pixel_size/2, maxx, pixel_size)
        y_coords = np.arange(miny + pixel_size/2, maxy, pixel_size)
        if x_coords.size == 0 or y_coords.size == 0:
            raise ValueError("pixel_size demasiado grande para los límites de la capa")
        xx, yy = np.meshgrid(x_coords, y_coords[::-1])  # note: invertimos y para raster origin arriba
        points_grid = np.column_stack((xx.ravel(), yy.ravel()))

        # 4. interpolación
        if method in ('linear', 'nearest', 'cubic'):
            pts = np.column_stack((xs, ys))
            zi = griddata(pts, vals, (points_grid[:,0], points_grid[:,1]), method=method)
        elif method == 'idw':
            # IDW manual: cuidado con coste si muchos puntos/grilla grande
            pts = np.column_stack((xs, ys))
            # distancia entre cada grid point y estaciones (M x N), M gridpoints, N estaciones
            # para memoria grande, podrías chunkificar; aquí asume tamaño razonable
            d = np.sqrt(((points_grid[:,None,0] - pts[None,:,0])**2) + ((points_grid[:,None,1] - pts[None,:,1])**2))
            d[d == 0] = 1e-10
            w = 1.0 / (d**idw_power)
            zi = (w * vals[None,:]).sum(axis=1) / w.sum(axis=1)
        else:
            raise ValueError("method debe ser 'linear','nearest','cubic' o 'idw'")

        # 5. formar array 2D y manejar nodata
        ny = y_coords.size
        nx = x_coords.size
        arr = zi.reshape((ny, nx))
        # griddata devuelve nan donde no puede interpolar (ej. extrapolación); mantener nodata
        # convertir nodata a valor numérico si usas nodata != np.nan
        if np.isnan(nodata):
            mask_nodata = np.isnan(arr)
        else:
            mask_nodata = np.isnan(arr)
            arr = np.where(mask_nodata, nodata, arr)

        # 6. crear transform (origen superior izquierda)
        origin_x = x_coords.min() - pixel_size/2.0
        origin_y = y_coords.max() + pixel_size/2.0
        transform = from_origin(origin_x, origin_y, pixel_size, pixel_size)

        # 7. escribir GeoTIFF
        meta = {
            'driver': 'GTiff',
            'height': arr.shape[0],
            'width': arr.shape[1],
            'count': 1,
            'dtype': dtype,
            'crs': target_crs,
            'transform': transform,
            'nodata': nodata,
            'compress': 'lzw'
        }
        with rasterio.open(out_tif, 'w', **meta) as dst:
            dst.write(arr.astype(dtype), 1)

        return out_tif

    def procesar(self):
        """Método principal siguiendo la lógica exacta del notebook"""
        logger.info("=== Iniciando procesamiento GeoTIFF (siguiendo notebook) ===")

        try:
            # Verificar archivo de entrada
            archivo_gpkg = self.input_path / 'prob_deslizamientos.gpkg'
            if not archivo_gpkg.exists():
                logger.error(f"Archivo no encontrado: {archivo_gpkg}")
                return False

            # Leer geopackage en un geodataframe (exacto al notebook)
            logger.info("Leyendo geopackage...")
            gdf = gpd.read_file(archivo_gpkg)
            logger.info(f"Geodataframe cargado: {len(gdf)} puntos")

            # Crear directorio de salida
            self.output_path.mkdir(parents=True, exist_ok=True)

            # Definir la ruta de salida (como en el notebook)
            ruta_salida = self.output_path / 'prob_geotif.tif'

            # Llamar función (exacto al notebook)
            logger.info("Ejecutando interpolación...")
            resultado = self.interpolate_geotiff(gdf, 'prob_ep', str(ruta_salida),
                                               target_crs='EPSG:3116',
                                               pixel_size=2000,    # p.ej. 2 km
                                               method='idw',
                                               idw_power=3)    # o 'nearest' o 'idw'

            logger.info(f"GeoTIFF guardado en: {resultado}")
            # Copiar resultado al volumen de uploads de GeoServer si existe
            try:
                uploads_path = Path('/mnt/uploads')
                if uploads_path.exists() and uploads_path.is_dir():
                    # Usar siempre el mismo nombre para que se sobrescriba automáticamente
                    dest_name = "prob_geotif.tif"
                    dest_path = uploads_path / dest_name
                    logger.info(f"Copiando GeoTIFF a uploads de GeoServer: {dest_path}")
                    # copiar archivo (sobreescribir si existe)
                    with open(resultado, 'rb') as src_f, open(dest_path, 'wb') as dst_f:
                        dst_f.write(src_f.read())
                    logger.info(f"GeoTIFF actualizado en: {dest_path}")
                else:
                    logger.debug("No existe /mnt/uploads; salto copia a GeoServer")
            except Exception as e:
                logger.error(f"Error copiando GeoTIFF a uploads de GeoServer: {e}")
            logger.info("=== Procesamiento GeoTIFF completado exitosamente ===")
            return True

        except Exception as e:
            logger.error(f"Error en procesamiento: {e}")
            return False

def _main():
    """Función principal del servicio - siguiendo notebook"""
    logger.info("=== Iniciando SAT GeoTIFF Exporter ===")

    try:
        # Inicializar exporter
        exporter = GeoTIFFExporter()

        # Procesar usando lógica del notebook
        if exporter.procesar():
            logger.info("Procesamiento exitoso")
            return 0
        else:
            logger.error("Error en procesamiento")
            return 1

    except Exception as e:
        logger.error(f"Error fatal en exportación: {e}")
        return 1

if __name__ == "__main__":
    exit_code = _main()
    sys.exit(exit_code)
