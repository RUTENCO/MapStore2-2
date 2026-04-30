import firebase_admin
from firebase_admin import credentials, db
import os
import sys
from datetime import datetime

import glob
import json
import logging
import os.path
import numpy as np
from pathlib import Path

np.int = int
import pandas as pd
import geopandas as gpd
import rasterio
import rasterio.features
import pickle
from geo.Geoserver import Geoserver
import io
from contextlib import redirect_stdout
import matplotlib
from shapely.geometry import Point

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.metrics import (
    confusion_matrix,
    classification_report,
    roc_curve,
    roc_auc_score,
    average_precision_score,
    brier_score_loss,
    precision_recall_curve,
)
from sklearn.model_selection import GroupKFold

from sklearn.preprocessing import StandardScaler
from pygam import LogisticGAM, s, f
from pygam.terms import TermList

import geopandas as gpd
import numpy as np
from datetime import datetime
from osgeo import gdal


def load_config():
    base_dir = Path(__file__).resolve().parent
    config_path = base_dir / "config.json"

    if not config_path.exists():
        raise FileNotFoundError(f"File {config_path} not found")

    with config_path.open(encoding="utf-8") as config_file:
        config = json.load(config_file)

    default_data_root = base_dir.parent.parent / "static" / "datalake"
    data_root = Path(os.getenv("MODEL_DATA_ROOT", config.get("data_root", default_data_root)))
    if not data_root.is_absolute():
        data_root = (default_data_root / data_root).resolve()

    config["data_root"] = str(data_root)

    path_keys = {
        "logs_dir",
        "credentials_firebase",
        "stagging_dir",
        "ingested_dir",
        "img_results_dir",
        "files_df_dir",
        "geodata_raster_dir",
        "geodata_raster_aoi_dir",
        "geodata_raster_results_dir",
        "geodata_geojson_dir",
        "shp_geojson_dir",
        "models_dir",
    }

    for key in path_keys:
        if key not in config:
            continue

        path_value = Path(config[key])
        if not path_value.is_absolute():
            path_value = data_root / path_value
        config[key] = str(path_value.resolve())

    return config


def ensure_runtime_directories(config):
    for key, value in config.items():
        if key.endswith("_dir"):
            Path(value).mkdir(parents=True, exist_ok=True)

    Path(config["credentials_firebase"]).parent.mkdir(parents=True, exist_ok=True)


def setup_logging(config):
    logging.basicConfig(
        filename=os.path.join(config["logs_dir"], config["create_database_log"]),
        level=logging.INFO,
        format="%(asctime)s:%(levelname)s:%(message)s",
    )


def main():
    print(f"[{datetime.now()}] Iniciando tarea programada...")

    try:
        config = load_config()
        ensure_runtime_directories(config)
        setup_logging(config)

        train_and_run_model_functions(config)

        print(f"[{datetime.now()}] Tarea finalizada con éxito.")
    except Exception as e:
        print(f"[{datetime.now()}] Error en la ejecución: {e}")
        sys.exit(1)  # Indica a Docker que algo salió mal


def train_and_run_model_functions(config):
    selected_vars = [
        "aspect",
        "curvature",
        "dem",
        "geo",
        # "landscapes",
        "slopes",
    ]
    df = extract(config, selected_vars)
    model, threshold_70, threshold_98 = train_model(
        config,
        df,
        selected_vars,
    )

    save_model_to_disk(model, config)
    # aux_75 = 0.5038
    # aux_98 = 0.1504
    run_model_functions(config, selected_vars, threshold_70, threshold_98)


def save_model_to_disk(model, config):
    """Save the model to the disk"""

    path = os.path.join(config["models_dir"], "mass_mov_model.pkl")
    with open(path, "wb") as file:
        pickle.dump(model, file)
    #
    logging.info("Model saved")
    #


def load_model_from_disk(config):
    """Load the model from the disk"""

    path = os.path.join(config["models_dir"], f"mass_mov_model.pkl")
    if os.path.exists(path):
        model = pd.read_pickle(path)
        #
        logging.info("Model loaded")
        #
    else:
        #
        logging.info("There is no model to load")
        #
        model = None

    return model


def descargar_datos_firebase(config):

    logging.info("Starting data download from Firebase")
    #
    # Ruta al archivo JSON de tu Service Account
    cred = credentials.Certificate(config["credentials_firebase"])

    # Inicializa la app con la URL de tu Realtime Database
    firebase_admin.initialize_app(
        cred, {"databaseURL": "https://geohazards-unal-default-rtdb.firebaseio.com/"}
    )

    # Referencia al nodo que quieres leer
    ref_col = db.reference("col")
    ref_ant = db.reference("ant")
    ref_sensores = db.reference("sensores_ant")

    # Leer todos los datos
    data_col = ref_col.get()
    data_ant = ref_ant.get()
    data_sensores = ref_sensores.get()

    # Crear un DataFrame
    df_ant = pd.DataFrame(data_ant)
    df_col = pd.DataFrame(data_col)
    df_col = df_col[df_col["department"] == "Antioquia"]
    df_sensores = pd.DataFrame(data_sensores)

    logging.info("Data download completed")
    #

    # Crear la geometría
    df_ant["geometry"] = df_ant.apply(lambda row: Point(row["lng"], row["lat"]), axis=1)
    df_ant = df_ant.drop(columns=["add"])
    df_col["geometry"] = df_col.apply(lambda row: Point(row["lng"], row["lat"]), axis=1)
    df_col = df_col.drop(columns=["add"])
    df_sensores["geometry"] = df_sensores.apply(
        lambda row: Point(row["lng"], row["lat"]), axis=1
    )

    # Convertir a GeoDataFrame con CRS WGS84 (EPSG:4326)
    gdf_geohazards = gpd.GeoDataFrame(
        pd.concat([df_ant, df_col, df_sensores]), geometry="geometry", crs="EPSG:4326"
    )
    gdf_geohazards.to_file(
        os.path.join(config["geodata_geojson_dir"], config["geojson_events_name"]),
        driver="GeoJSON",
    )


    logging.info("Events GeoJSON file created")
    #

    pass


def create_empty_raster(config):
    """Creates an empty raster file"""
    #
    logging.info("Starting empty raster creation")
    #

    raster_dem_path = os.path.join(
        config["geodata_raster_dir"], config["raster_dem_name"]
    )

    with rasterio.open(raster_dem_path) as src:
        transform = src.transform
        rows = src.height
        columns = src.width
        band = src.read(1)
        crs = src.crs
        nodata_value = src.nodata

    # new_raster = np.zeros((rows, columns), dtype=band.dtype)
    new_raster = np.where(band != nodata_value, 0, nodata_value)
    raster_empty_path = ""
    raster_empty_path = os.path.join(
        config["geodata_raster_dir"], config["raster_empty_name"]
    )
    with rasterio.open(
        raster_empty_path,
        "w",
        driver="GTiff",
        width=columns,
        height=rows,
        count=1,
        dtype="int8",
        nodata=-15,
        crs=crs,
        transform=transform,
    ) as dst:
        dst.write(new_raster, 1)
    #
    del band
    del new_raster
    logging.info("Empty raster creation completed")


def create_events_buffer_raster(config):
    """Creates the events buffer raster file"""
    #
    logging.info("Starting events buffer raster creation")
    #
    # Create a buffer around inventory points
    points_gdf = None
    geojson_events_path = os.path.join(
        config["geodata_geojson_dir"], config["geojson_events_name"]
    )
    points_gdf = gpd.read_file(geojson_events_path)

    if points_gdf.crs is None:
        points_gdf.set_crs(epsg=32618, inplace=True)

    buffer_points_gdf = points_gdf.to_crs("EPSG:32618")
    buffer_points_gdf["geometry"] = buffer_points_gdf.geometry.buffer(40)

    buffer_points_gdf = buffer_points_gdf.to_crs("EPSG:4326")
    for column in buffer_points_gdf.columns:
        if buffer_points_gdf[column].dtype == "object":
            buffer_points_gdf[column] = buffer_points_gdf[column].apply(
                lambda x: x.decode("utf-8") if isinstance(x, bytes) else x
            )

    raster_empty_path = os.path.join(
        config["geodata_raster_dir"], config["raster_empty_name"]
    )

    with rasterio.open(raster_empty_path) as src:
        profile = src.profile
        transform = src.transform
        crs = src.crs
        raster_data = src.read(1)

    shapes = (
        (geom, 1) for geom in buffer_points_gdf.geometry
    )  # Generar pares (geometría, valor)
    rasterized = rasterio.features.rasterize(
        shapes,
        out_shape=raster_data.shape,
        transform=profile["transform"],
        fill=0,  # Valor para las celdas fuera de los polígonos
        dtype=raster_data.dtype,
    )

    # 5. Asignar el rasterizado al raster base
    raster_data[rasterized == 1] = 1

    raster_events_path = os.path.join(
        config["geodata_raster_dir"], config["raster_buffer_events_name"]
    )

    with rasterio.open(
        raster_events_path,
        "w",
        driver="GTiff",
        width=raster_data.shape[1],
        height=raster_data.shape[0],
        count=1,
        dtype=raster_data.dtype,
        crs=crs,
        transform=transform,
        nodata=-15,
    ) as dst:
        dst.write(raster_data, 1)

    del raster_data
    del points_gdf
    del buffer_points_gdf

    #
    logging.info("Events buffer raster creation completed")


def create_events_raster(config):
    """Creates the events raster file"""
    #
    logging.info("Starting events raster creation")
    #

    raster_empty_path = os.path.join(
        config["geodata_raster_dir"], config["raster_empty_name"]
    )

    with rasterio.open(raster_empty_path) as src:
        transform = src.transform
        crs = src.crs
        raster_data = src.read(1)

    points_gdf = None

    geojson_events_path = os.path.join(
        config["geodata_geojson_dir"], config["geojson_events_name"]
    )
    points_gdf = gpd.read_file(geojson_events_path)

    if points_gdf.crs is None:
        points_gdf.set_crs(epsg=4326, inplace=True)
    else:
        points_gdf = points_gdf.to_crs(crs)

    height, width = raster_data.shape

    for point in points_gdf.geometry:
        x, y = point.x, point.y
        row, col = src.index(x, y)
        if 0 <= row < height and 0 <= col < width:
            raster_data[row, col] = 1

    raster_events_path = os.path.join(
        config["geodata_raster_dir"], config["raster_events_name"]
    )

    with rasterio.open(
        raster_events_path,
        "w",
        driver="GTiff",
        width=raster_data.shape[1],
        height=raster_data.shape[0],
        count=1,
        dtype=raster_data.dtype,
        crs=crs,
        transform=transform,
        nodata=-15,
    ) as dst:
        dst.write(raster_data, 1)

    del raster_data

    #
    logging.info("Events raster creation completed")


def make_block_ids(
    height: int, width: int, n_row_blocks: int = 5, n_col_blocks: int = 5
) -> np.ndarray:
    """
    Asigna IDs de bloque (grilla n_row_blocks x n_col_blocks) a cada píxel de una malla (height x width).
    Retorna un vector 1D (flatten) con el block_id por píxel.
    """

    logging.info("Starting make block ids")
    rr, cc = np.indices((height, width))
    row_bin_size = max(1, height // n_row_blocks)
    col_bin_size = max(1, width // n_col_blocks)
    rbin = rr // row_bin_size
    cbin = cc // col_bin_size
    rbin = np.minimum(rbin, n_row_blocks - 1)
    cbin = np.minimum(cbin, n_col_blocks - 1)
    block_id = (rbin * n_col_blocks + cbin).astype(np.int32)
    logging.info("Make block ids completed")
    return block_id.ravel()


def extract_raster_data(config, selected_vars):
    """Extracts data from raster files"""
    #
    logging.info("Starting raster data extraction")
    #
    df_combined = pd.DataFrame()
    columns_dict = {}

    path = os.path.join(config["geodata_raster_dir"], "*.tif")

    filenames = glob.glob(path)
    filtered_filenames = [
        file
        for file in filenames
        if os.path.splitext(os.path.basename(file))[0] in selected_vars
    ]

    filtered_filenames.append(os.path.join(config["geodata_raster_dir"], "events.tif"))
    filtered_filenames.append(
        os.path.join(config["geodata_raster_dir"], "buffer_events.tif")
    )

    print(filtered_filenames)

    for file in filtered_filenames:
        with rasterio.open(file) as src:
            logging.info(f"Data {file} extraction")

            raster_dtype = src.dtypes[0]
            logging.info(f"El tipo de dato del raster es: {raster_dtype}")

            if os.path.basename(file) == "landscapes.tif":
                raster_data = src.read(1).astype(np.int8)
            else:
                raster_data = src.read(1)
            nodata_value = src.nodata
            logging.info(f"El no data del raster es: {nodata_value}")

            columns_dict[os.path.splitext(os.path.basename(file))[0]] = (
                raster_data.ravel()
            )

            logging.info(f"Data {file} extracted")
        del raster_data
        # del raster_data, df_aux

    logging.info(f"Start creating dataframe")
    df_combined = pd.DataFrame(columns_dict)
    logging.info(f"Dataframe created")

    del columns_dict

    dem_path = os.path.join(config["geodata_raster_dir"], config["raster_dem_name"])

    with rasterio.open(dem_path) as src_dem:
        height, width = src_dem.height, src_dem.width

    # Asignar block_id por defecto con grilla 5x5 (ajustable si se desea)
    block_ids = make_block_ids(height, width, n_row_blocks=5, n_col_blocks=5)
    df_combined["block_id"] = block_ids

    #
    logging.info("Raster data extraction completed")
    #

    return df_combined


def extract(config, selected_vars):
    """Extracts dataframe events and no-events"""

    logging.info("Starting data extraction")
    #

    df_complete = pd.DataFrame()

    descargar_datos_firebase(config)
    create_empty_raster(config)
    create_events_raster(config)
    create_events_buffer_raster(config)
    df_complete = extract_raster_data(config, selected_vars)

    # df_complete_aux = df_complete.dropna(axis=0)
    df_complete_aux = df_complete[~(df_complete == -15).any(axis=1)]

    del df_complete
    df_events = df_complete_aux.loc[df_complete_aux["events"] == 1]
    if "landscapes" in df_complete_aux.columns:
        df_events = df_complete_aux.loc[
            # (df_complete_aux["events"] == 1) & (df_complete_aux["landscapes"] != 5)
            (df_complete_aux["events"] == 1)
        ]

    events_count = df_events["events"].count()
    logging.info(f"Pixel events count: {events_count}")

    df_no_events = df_complete_aux[
        (df_complete_aux["events"] == 0) & (df_complete_aux["buffer_events"] == 0)
    ].sample(n=events_count, random_state=420)

    no_events_count = df_no_events["events"].count()
    logging.info(f"Pixel no events count: {no_events_count}")

    # Verificar columnas categóricas
    for column in ["landscapes", "geo"]:
        if column in df_complete_aux.columns:
            full_set = set(df_complete_aux[column].unique())
            current_set = set(df_no_events[column].unique())

            # Verificar si faltan valores
            missing_values = full_set - current_set

            if missing_values:
                logging.info(f"[INFO] Faltan valores en '{column}': {missing_values}")

                new_rows = []

                for missing_value in missing_values:
                    match = df_complete_aux[
                        (df_complete_aux["events"] == 0)
                        & (df_complete_aux["buffer_events"] == 0)
                        & (df_complete_aux[column] == missing_value)
                    ]

                    if not match.empty:
                        new_rows.append(
                            match.iloc[0]
                        )  # tomar solo una fila representativa

                if new_rows:
                    df_no_events = pd.concat(
                        [df_no_events, pd.DataFrame(new_rows)], ignore_index=True
                    )

    no_events_count = df_no_events["events"].count()
    logging.info(f"Pixel no events count: {no_events_count}")
    columns = df_complete_aux.columns.tolist()
    del df_complete_aux
    df = pd.merge(df_events, df_no_events, on=columns, how="outer")
    df.drop("buffer_events", axis=1, inplace=True)
    #
    logging.info("Data extraction completed")
    #

    return df


def pad_categories_for_gam(
    X_tr: pd.DataFrame,
    y_tr: pd.Series,
    full_cats: dict[str, set],
    cont_cols: list[str],
    cat_cols: list[str],
    epsilon_weight: float = 1e-6,
):
    """
    Inserta filas sintéticas de muy bajo peso para que pyGAM f() registre
    todas las categorías globales en el pliegue de entrenamiento.
    """
    # Estadísticos de referencia en train
    cont_medians = {}
    for c in cont_cols:
        if c in X_tr.columns:
            # usar mediana robusta
            cont_medians[c] = float(np.nanmedian(X_tr[c].values))

    cat_modes = {}
    for c in cat_cols:
        if c in X_tr.columns and not X_tr[c].dropna().empty:
            cat_modes[c] = int(pd.Series(X_tr[c].dropna()).mode().iloc[0])
        elif c in full_cats and len(full_cats[c]) > 0:
            # fallback: primera categoría global
            cat_modes[c] = int(sorted(list(full_cats[c]))[0])

    rows = []
    ys = []
    ws = []

    for c in cat_cols:
        if c not in X_tr.columns:
            continue
        seen = set(pd.unique(X_tr[c].dropna()))
        missing = full_cats.get(c, set()) - seen
        for m in missing:
            new_row = {}
            # valores por defecto para cada columna
            for col in X_tr.columns:
                if col in cont_medians:
                    new_row[col] = cont_medians[col]
                elif col in cat_cols:
                    new_row[col] = cat_modes.get(col, list(full_cats.get(col, {0}))[0])
                else:
                    # cualquier otra: usar mediana como continuo
                    new_row[col] = float(np.nanmedian(X_tr[col].values))
            # fijar la categoría faltante en su columna
            new_row[c] = int(m)
            rows.append(new_row)
            ys.append(int(pd.Series(y_tr).mode().iloc[0]) if not y_tr.empty else 0)
            ws.append(epsilon_weight)

    if rows:
        X_pad = pd.DataFrame(rows)[X_tr.columns]  # preservar orden de columnas
        X_aug = pd.concat([X_tr, X_pad], ignore_index=True)
        y_aug = pd.concat(
            [y_tr.reset_index(drop=True), pd.Series(ys)], ignore_index=True
        )
        w = np.concatenate([np.ones(len(y_tr)), np.array(ws, dtype=float)])
        return X_aug, y_aug, w
    else:
        return X_tr, y_tr, np.ones(len(y_tr), dtype=float)


def get_full_category_sets(X: pd.DataFrame, cat_cols: list[str]) -> dict[str, set]:
    """
    Devuelve el conjunto global de categorías observadas por columna categórica.
    """
    full = {}
    for c in cat_cols:
        if c in X.columns:
            full[c] = set(pd.unique(X[c].dropna()))
    return full


def gam_spatial_grid_search(
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    n_splits: int = 5,
    lam_grid: list[float] = (0.1, 0.3, 0.6, 1.0, 3.0),
    n_splines_grid: list[int] = (8, 10, 15, 20),
    max_iter: int = 200,
    scoring: str = "ap",  # "ap" (Average Precision) o "auc"
) -> dict:
    """
    Búsqueda de hiperparámetros para GAM con validación cruzada espacial (GroupKFold).
    Evalúa todas las combinaciones (lam, n_splines) y retorna el mejor dict.
    Mantiene padding de categorías por pliegue para evitar fallos en f() de pyGAM.
    """
    #
    logging.info("Starting GAM hyperparameter tuning with spatial CV function")
    #

    cont_cols = [c for c in X.columns if c in ["aspect", "slopes", "dem"]]
    cat_cols = [c for c in X.columns if c in ["landscapes", "geo", "curvature"]]
    full_cats = get_full_category_sets(X, cat_cols)

    gkf = GroupKFold(n_splits=n_splits)
    best = {"score": -np.inf, "lam": None, "n_splines": None}

    #
    logging.info("Starting GAM hyperparameter grid search")
    #

    for lam in lam_grid:
        for ns in n_splines_grid:
            fold_scores = []
            for tr_idx, te_idx in gkf.split(X, y, groups=groups):
                X_tr, X_te = X.iloc[tr_idx], X.iloc[te_idx]
                y_tr, y_te = y.iloc[tr_idx], y.iloc[te_idx]
                if y_te.nunique() < 2 or y_tr.nunique() < 2:
                    continue

                # Términos
                terms = []
                for j, v in enumerate(X.columns.tolist()):
                    if v in cont_cols:
                        terms.append(s(j, n_splines=ns, lam=lam))
                    elif v in cat_cols:
                        terms.append(f(j, lam=lam))

                gam = LogisticGAM(TermList(*terms), max_iter=max_iter)

                # Padding categórico
                X_tr_aug, y_tr_aug, w = pad_categories_for_gam(
                    X_tr.copy(),
                    y_tr.copy(),
                    full_cats,
                    cont_cols,
                    cat_cols,
                    epsilon_weight=1e-6,
                )

                gam.fit(X_tr_aug, y_tr_aug, weights=w)
                y_prob = gam.predict_proba(X_te)

                if scoring.lower() == "ap":
                    score = average_precision_score(y_te, y_prob)
                else:
                    score = roc_auc_score(y_te, y_prob)
                fold_scores.append(score)

            if fold_scores:
                mean_score = float(np.mean(fold_scores))
                if mean_score > best["score"]:
                    best = {
                        "score": mean_score,
                        "lam": float(lam),
                        "n_splines": int(ns),
                    }

    if best["lam"] is None:
        # Fallback seguro si algo falló
        best = {"score": np.nan, "lam": 0.6, "n_splines": 10}
        #
        logging.info("GAM hyperparameter grid search completed")
        #
    #
    logging.info("GAM hyperparameter tuning with spatial CV function completed")
    #
    return {
        "lam": best["lam"],
        "n_splines": best["n_splines"],
        "max_iter": int(max_iter),
    }


def compute_metrics(y_true, y_prob):
    """
    Retorna dict con AUC-ROC, PR-AUC (average precision), Brier, Sensibilidad y Especificidad
    usando umbral 0.5 solo para sensibilidad/especificidad de referencia (no reclasificación operativa).
    """
    fpr, tpr, _ = roc_curve(y_true, y_prob)
    auc = roc_auc_score(y_true, y_prob)
    ap = average_precision_score(y_true, y_prob)
    brier = brier_score_loss(y_true, y_prob)
    y_pred05 = (y_prob >= 0.5).astype(int)
    cm = confusion_matrix(y_true, y_pred05)
    tn, fp, fn, tp = cm.ravel()
    sens = tp / (tp + fn) if (tp + fn) > 0 else np.nan
    spec = tn / (tn + fp) if (tn + fp) > 0 else np.nan
    return {"auc": auc, "ap": ap, "brier": brier, "sens@0.5": sens, "spec@0.5": spec}


def spatial_cv_predict_proba(hiperparameters, X, y, groups, n_splits):
    """
    Realiza k-fold espacial (GroupKFold) y retorna y_true/y_prob concatenados OOF,
    más métricas por pliegue.
    """
    logging.info("Start spatial cross-validation prediction")

    gkf = GroupKFold(n_splits=n_splits)
    y_true_all, y_prob_all = [], []
    fold_metrics = []

    # Definir columnas continuas/categóricas
    cont_cols = [c for c in X.columns if c in ["aspect", "slopes", "dem"]]
    cat_cols = [c for c in X.columns if c in ["landscapes", "geo", "curvature"]]

    # Conjuntos globales de categorías
    full_cats = get_full_category_sets(X, cat_cols)

    for fold, (tr_idx, te_idx) in enumerate(gkf.split(X, y, groups=groups), start=1):
        X_tr, X_te = X.iloc[tr_idx], X.iloc[te_idx]
        y_tr, y_te = y.iloc[tr_idx], y.iloc[te_idx]

        # Evitar conjuntos sin ambas clases
        if y_te.nunique() < 2 or y_tr.nunique() < 2:
            logging.info(
                f"[CV-Spatial] Fold {fold} saltado por falta de clases en train/test"
            )
            continue

        # Construcción dinámica de términos
        terms = []
        idx = 0
        for v in X.columns.tolist():
            if v in cont_cols:
                terms.append(
                    s(
                        idx,
                        n_splines=hiperparameters.get("n_splines", 10),
                        lam=hiperparameters.get("lam", 0.6),
                    )
                )
            elif v in cat_cols:
                terms.append(f(idx, lam=hiperparameters.get("lam", 0.6)))
            idx += 1
        model = LogisticGAM(
            TermList(*terms), max_iter=hiperparameters.get("max_iter", 100)
        )

        # Asegurar dominio categórico completo en el fold de entrenamiento
        X_tr_aug, y_tr_aug, w = pad_categories_for_gam(
            X_tr.copy(),
            y_tr.copy(),
            full_cats,
            cont_cols,
            cat_cols,
            epsilon_weight=1e-6,
        )
        model.fit(X_tr_aug, y_tr_aug, weights=w)
        y_prob = model.predict_proba(X_te)

        # Agregar resultados del pliegue
        y_true_all.append(y_te.values)
        y_prob_all.append(y_prob)
        # compute_metrics debe existir; si no, crea una versión mínima
        fold_metrics.append(compute_metrics(y_te.values, y_prob))

    y_true_all = np.concatenate(y_true_all) if len(y_true_all) else np.array([])
    y_prob_all = np.concatenate(y_prob_all) if len(y_prob_all) else np.array([])

    return y_true_all, y_prob_all, fold_metrics


def plot_roc_curve(y_test, y_probs, save_path):
    fpr, tpr, thresholds = roc_curve(y_test, y_probs)
    auc_score = roc_auc_score(y_test, y_probs)

    target_tpr = 0.75
    index = np.argmin(np.abs(tpr - target_tpr))
    threshold_75 = thresholds[index]
    # tpr_70 = tpr[index]
    target_tpr = 0.98
    index = np.argmin(np.abs(tpr - target_tpr))
    threshold_98 = thresholds[index]
    # tpr_98 = tpr[index]

    plt.figure(figsize=(6, 4))
    plt.plot(fpr, tpr, label=f"AUC = {auc_score:.2f}", color="blue")
    plt.plot([0, 1], [0, 1], "r--", label="Aleatorio")
    plt.xlabel("Tasa de Falsos Positivos")
    plt.ylabel("Tasa de Verdaderos Positivos")
    plt.title("Curva ROC")
    plt.legend()
    plt.tight_layout()
    plt.savefig(save_path)
    plt.close()

    return threshold_75, threshold_98


def youden_threshold(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """
    Umbral que maximiza el índice de Youden J = TPR - FPR sobre la curva ROC.
    Devuelve el threshold escalar.
    """
    fpr, tpr, thr = roc_curve(y_true, y_prob)
    j = tpr - fpr
    return thr[np.argmax(j)]


def threshold_at_tpr(
    y_true: np.ndarray, y_prob: np.ndarray, target_tpr: float = 0.98
) -> float:
    fpr, tpr, thr = roc_curve(y_true, y_prob)
    idx = int(np.argmin(np.abs(tpr - target_tpr)))
    return float(thr[idx])


def plot_confusion_matrix(y_test, y_pred, save_path):
    cm = confusion_matrix(y_test, y_pred)
    plt.figure(figsize=(6, 4))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Pastel1", cbar=False)
    plt.title("Matriz de Confusión")
    plt.xlabel("Predicción")
    plt.ylabel("Verdadero")
    plt.tight_layout()
    plt.savefig(save_path)
    plt.close()


def save_classification_report(y_test, y_pred, save_path):
    report = classification_report(y_test, y_pred, output_dict=True)
    plt.figure(figsize=(8, 4))
    sns.heatmap(pd.DataFrame(report).iloc[:-1, :].T, annot=True, cmap="Blues")
    plt.title("Reporte de Clasificación")
    plt.tight_layout()
    plt.savefig(save_path)
    plt.close()


def confusion_and_report_oof(
    y_true_all: np.ndarray,
    y_prob_all: np.ndarray,
    threshold: float,
    path_cm: str,
    path_cr: str,
) -> dict:
    """
    Calcula matriz de confusión y classification_report sobre predicciones OOF.
    Guarda las figuras con tus funciones existentes y retorna métricas básicas.
    """
    y_pred_all = (y_prob_all >= threshold).astype(int)
    # Graficar/guardar
    plot_confusion_matrix(y_true_all, y_pred_all, path_cm)
    save_classification_report(y_true_all, y_pred_all, path_cr)

    # Métricas rápidas
    fpr, tpr, _ = roc_curve(y_true_all, y_prob_all)
    auc = roc_auc_score(y_true_all, y_prob_all)
    ap = average_precision_score(y_true_all, y_prob_all)
    brier = brier_score_loss(y_true_all, y_prob_all)
    # Sens/Spec al umbral usado
    cm = confusion_matrix(y_true_all, y_pred_all)
    tn, fp, fn, tp = cm.ravel()
    sens = tp / (tp + fn) if (tp + fn) else np.nan
    spec = tn / (tn + fp) if (tn + fp) else np.nan
    return {
        "threshold": float(threshold),
        "auc": float(auc),
        "ap": float(ap),
        "brier": float(brier),
        "sens": float(sens),
        "spec": float(spec),
    }


def plot_pr_curve_oof(
    y_true_all: np.ndarray, y_prob_all: np.ndarray, save_path: str
) -> float:
    """
    Traza la PR curve sobre OOF y devuelve el Average Precision (AP).
    """
    precision, recall, _ = precision_recall_curve(y_true_all, y_prob_all)
    ap = average_precision_score(y_true_all, y_prob_all)
    plt.figure(figsize=(6, 4))
    plt.plot(recall, precision, color="green", label=f"AP = {ap:.2f}")
    # Línea base = prevalencia positiva en OOF
    base = (y_true_all == 1).mean()
    plt.hlines(
        base,
        0,
        1,
        colors="gray",
        linestyles="--",
        label=f"Base (prevalencia) = {base:.2f}",
    )
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.title("Curva Precisión-Recall (OOF)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(save_path)
    plt.close()
    return float(ap)


def save_cv_metrics_table_image(
    df: pd.DataFrame, out_path: str, title: str | None = None
):
    """
    Lee un CSV de métricas por pliegue (fold) y guarda una imagen tipo tabla (PNG).
    Espera columnas como: ['auc','ap','brier','sens@0.5','spec@0.5'] (puede contener más).
    Agrega una fila de resumen con 'Mean ± SD' para cada métrica numérica.
    """
    # df = pd.read_csv(csv_path)

    # Inserta columna Fold si no existe
    if "Fold" not in df.columns:
        df.insert(0, "Fold", np.arange(1, len(df) + 1))

    # Orden sugerido de columnas si están presentes
    preferred_order = ["Fold", "auc", "ap", "brier", "sens@0.5", "spec@0.5"]
    cols = [c for c in preferred_order if c in df.columns] + [
        c for c in df.columns if c not in preferred_order
    ]
    df = df[cols]

    # Fila de resumen "Mean ± SD" para columnas numéricas (excepto 'Fold')
    numeric_cols = [
        c for c in df.columns if c != "Fold" and np.issubdtype(df[c].dtype, np.number)
    ]
    summary = {c: f"{df[c].mean():.3f} ± {df[c].std(ddof=1):.3f}" for c in numeric_cols}
    summary["Fold"] = "Mean ± SD"

    # Redondeo de celdas numéricas por legibilidad
    df_display = df.copy()
    for c in numeric_cols:
        df_display[c] = df_display[c].map(lambda x: f"{x:.3f}")

    df_display = pd.concat([df_display, pd.DataFrame([summary])], ignore_index=True)

    # Tamaño de figura: escala con filas/columnas
    n_rows, n_cols = df_display.shape
    fig_w = max(8, n_cols * 1.6)
    fig_h = max(2.5, n_rows * 0.6)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")

    # Render de tabla
    table = ax.table(
        cellText=df_display.values,
        colLabels=df_display.columns,
        cellLoc="center",
        loc="upper center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.2)

    # Estética: resalta la fila de resumen (última fila)
    last_row = n_rows - 1
    for j in range(n_cols):
        cell = table[last_row, j]
        cell.set_facecolor("#f0f4ff")  # azul muy claro
        cell.set_fontsize(10)
        cell.set_text_props(weight="bold")

    # Título opcional
    if title:
        ax.set_title(title, fontsize=12, pad=10)

    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def train_model(
    config,
    df,
    var_predict,
):
    """Train model"""

    n_splits = 5

    encontrado = any("aspect" in elemento for elemento in var_predict)
    if encontrado:
        df[["aspect"]] = StandardScaler().fit_transform(df[["aspect"]])
    encontrado = any("slopes" in elemento for elemento in var_predict)
    if encontrado:
        df[["slopes"]] = StandardScaler().fit_transform(df[["slopes"]])

    threshold_70, threshold_98 = None, None

    model = None

    X = df.drop(columns=["events"])
    X = X[var_predict].copy()
    y = df["events"].copy()

    groups = df["block_id"]

    #
    logging.info("Starting GAM hyperparameter tuning with spatial CV")
    #

    # Grid manual con GroupKFold (espacial)

    best_params_gam = gam_spatial_grid_search(
        X,
        y,
        groups,
        n_splits=n_splits,
        lam_grid=[0.1, 0.3, 0.6, 1.0, 2.0, 3.0, 4.0],
        n_splines_grid=[8, 10, 15, 20, 30],
        max_iter=400,
        scoring="auc",
    )

    #
    logging.info("GAM hyperparameter tuning with spatial CV completed")
    #

    hiperparameters = {**best_params_gam}

    #
    logging.info("Start calculating train & test datasets with Spatial CV")
    #

    y_true_all, y_prob_all, fold_metrics = spatial_cv_predict_proba(
        hiperparameters,
        X,
        y,
        groups,
        n_splits,
    )
    if y_prob_all.size == 0:
        #
        logging.info(
            "CV espacial no produjo predicciones válidas. Ajuste n_splits o el tamaño de bloques."
        )
        #
        raise RuntimeError(
            "CV espacial no produjo predicciones válidas. Ajuste n_splits o el tamaño de bloques."
        )

    # Plots y umbrales a partir de OOF
    path_roc = os.path.join(config["img_results_dir"], f"roc_curve.png")
    threshold_70, threshold_98 = plot_roc_curve(y_true_all, y_prob_all, path_roc)

    t_high = youden_threshold(
        y_true_all, y_prob_all
    )  # frontera Media/Alta (operación binaria base)
    t_low = threshold_at_tpr(y_true_all, y_prob_all, 0.98)

    cm_path = os.path.join(config["img_results_dir"], f"confusion_matrix.png")
    cr_path = os.path.join(config["img_results_dir"], f"classification_report.png")
    _ = confusion_and_report_oof(y_true_all, y_prob_all, t_high, cm_path, cr_path)

    # 3) Curva PR OOF
    pr_path = os.path.join(config["img_results_dir"], f"pr_curve.png")
    _ = plot_pr_curve_oof(y_true_all, y_prob_all, pr_path)

    # Guardar métricas promedio
    metrics_df = pd.DataFrame(fold_metrics)

    png_path = os.path.join(config["img_results_dir"], f"cv_spatial_metrics.png")
    save_cv_metrics_table_image(
        metrics_df, png_path, title=f"Métricas por conjunto (CV espacial, k={n_splits})"
    )

    # Para persistir el modelo: reentrena con TODO el dataset (bajo mismo hiperparámetro)
    model = None
    terms = []
    idx = 0
    for v in X.columns.tolist():
        if v in ["aspect", "slopes", "dem"]:
            terms.append(
                s(
                    idx,
                    n_splines=hiperparameters.get("n_splines", 10),
                    lam=hiperparameters.get("lam", 0.6),
                )
            )
        elif v in ["landscapes", "geo", "curvature"]:
            terms.append(f(idx, lam=hiperparameters.get("lam", 0.6)))
        idx += 1
    model = LogisticGAM(TermList(*terms), max_iter=hiperparameters.get("max_iter", 100))

    model.fit(X, y)

    log_buffer = io.StringIO()

    def save_summary_as_image(summary_text, filename):
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.axis("off")
        ax.text(
            0,
            1,
            summary_text,
            fontsize=10,
            verticalalignment="top",
            family="monospace",
        )
        plt.savefig(filename, bbox_inches="tight")
        plt.close()

    with redirect_stdout(log_buffer):
        model.summary()
    summary_text = log_buffer.getvalue()
    path = os.path.join(config["img_results_dir"], f"summary.png")
    save_summary_as_image(summary_text, path)
    #
    logging.info("Resumen del modelo:\n%s", summary_text)
    #

    return model, threshold_70, threshold_98


def extract_data(config, VAR_PREDICT):
    """Extracts data from raster files"""
    #
    logging.info("Starting raster data extraction")
    #

    # if IS_TRAINING:

    df_combined = pd.DataFrame()
    columns_dict = {}
    path_raster_aoi = os.path.join(config["geodata_raster_dir"])
    path = os.path.join(path_raster_aoi, "*.tif")
    filenames = glob.glob(path)

    filtered_filenames = [
        file
        for file in filenames
        if os.path.splitext(os.path.basename(file))[0] in VAR_PREDICT
    ]

    print(filtered_filenames)

    for file in filtered_filenames:
        with rasterio.open(file) as src:
            logging.info(f"Data {file} extraction")

            raster_dtype = src.dtypes[0]
            logging.info(f"El tipo de dato del raster es: {raster_dtype}")

            if os.path.basename(file) == "landscapes.tif":
                raster_data = src.read(1).astype(np.int8)
            else:
                raster_data = src.read(1)
            nodata_value = src.nodata
            logging.info(f"El no data del raster es: {nodata_value}")

            columns_dict[os.path.splitext(os.path.basename(file))[0]] = (
                raster_data.ravel()
            )

            logging.info(f"Data {file} extracted")
        del raster_data

    logging.info(f"Start creating dataframe")
    df_combined = pd.DataFrame(columns_dict)
    logging.info(f"Dataframe created")

    del columns_dict

    #
    logging.info("Raster data extraction completed")
    #

    return df_combined


def run_model_functions(config, selected_vars, THRESHOLD_75, THRESHOLD_98):
    """Run model"""

    #
    logging.info("Start run model")
    #
    model = load_model_from_disk(config)

    df_complete = extract_data(config, selected_vars)

    df_complete = df_complete.replace(-15, 1)

    encontrado = any("aspect" in elemento for elemento in selected_vars)
    if encontrado:
        df_complete[["aspect"]] = StandardScaler().fit_transform(
            df_complete[["aspect"]]
        )
    encontrado = any("slopes" in elemento for elemento in selected_vars)
    if encontrado:
        df_complete[["slopes"]] = StandardScaler().fit_transform(
            df_complete[["slopes"]]
        )

    df_complete = df_complete[selected_vars]

    chunk_size = 1000000
    total_rows = len(df_complete)
    resultados_proba = []

    logging.info("Start prediction")

    logging.info(f"Iniciando predicción por bloques para {total_rows} filas")

    for i in range(0, total_rows, chunk_size):
        # Extraer el pedazo actual
        chunk = df_complete.iloc[i : i + chunk_size].copy()

        # --- PREPROCESAMIENTO DEL CHUNK ---
        chunk = chunk.replace(-15, 1)

        if any("aspect" in e for e in selected_vars):
            chunk[["aspect"]] = StandardScaler().fit_transform(chunk[["aspect"]])

        if any("slopes" in e for e in selected_vars):
            chunk[["slopes"]] = StandardScaler().fit_transform(chunk[["slopes"]])

        chunk = chunk[selected_vars]
        # ----------------------------------

        # Predicción del bloque
        y_chunk_proba = model.predict_proba(chunk).astype(np.float32)

        # Aquí tienes dos opciones:
        # A. Guardar solo la probabilidad de la clase positiva (ahorra 50% de RAM)
        # B. Guardar el array completo
        # resultados_proba.append(y_chunk_proba)

        condiciones = [
            (y_chunk_proba < THRESHOLD_98),
            (y_chunk_proba >= THRESHOLD_98) & (y_chunk_proba <= THRESHOLD_75),
            (y_chunk_proba > THRESHOLD_75) & (y_chunk_proba <= 0.6),
            (y_chunk_proba > 0.6) & (y_chunk_proba <= 0.8),
            (y_chunk_proba > 0.8),
        ]
        valores = [1, 2, 3, 4, 5]

        chunk_reclass = np.select(condiciones, valores, default=0).astype(np.uint8)

        # Guardamos el resultado ya "comprimido"
        resultados_proba.append(chunk_reclass)

        logging.info(f"Procesado: {min(i + chunk_size, total_rows)} / {total_rows}")

    # Unir todos los resultados al final
    # y_pred_proba = np.vstack(resultados_proba)
    y_pred_proba = np.concatenate(resultados_proba, axis=0)

    #
    logging.info("Prediction executed")
    #

    path_raster = os.path.join(config["geodata_raster_dir"])
    raster_dem_path = os.path.join(path_raster, config["raster_dem_name"])
    raster_dem = rasterio.open(raster_dem_path)
    raster_aux = raster_dem.read(1)
    nodata_value = raster_dem.nodata
    IS = y_pred_proba.reshape(raster_aux.shape)
    IS = np.where(raster_aux == nodata_value, np.nan, IS)

    meta = raster_dem.profile
    raster_transform = meta["transform"]
    raster_crs = meta["crs"]

    raster_result_path = os.path.join(
        # config["geodata_raster_results_dir"], config["raster_result_name"] + datetime.now().strftime("%Y%m%d_%H%M%S") + ".tif"
        config["geodata_raster_results_dir"], config["raster_result_name"] + ".tif"
    )
    with rasterio.open(
        raster_result_path,
        "w",
        driver="Gtiff",
        height=raster_aux.shape[0],
        width=raster_aux.shape[1],
        count=1,
        dtype="float64",
        nodata=np.nan,
        crs=raster_crs,
        transform=raster_transform,
    ) as dst:
        dst.write(IS, 1)

    #
    logging.info("Results raster created")
    #

    # name_layer = f"susceptibility"

    # geo = Geoserver(
    #     "http://127.0.0.1:8080/geoserver", username="admin", password="geoserver"
    # )
    # geo.create_coveragestore(
    #     layer_name=name_layer, path=raster_result_path, workspace="tesis"
    # )
    # geo.publish_style(
    #     layer_name=name_layer, style_name="Raster Susceptibility", workspace="tesis"
    # )

    #
    # logging.info("Layer susceptibility published on Geoserver")
    #


if __name__ == "__main__":
    main()
