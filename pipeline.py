import os
import glob
from datetime import datetime
import pandas as pd
import geopandas as gpd
from tqdm import tqdm

from app.detection import DeforestacionDetector
from app.detection_detectron import Detectron2Detector
from app.deteccion_combinada import detectar_con_ambos_modelos_precisa
from app.geojson_utils import mostrar_mapa_amazonia_y_detecciones_unico_archivo


CARPETA_IMAGENES = os.path.join("app", "data")
RESULTS_GEOJSON = os.path.join("app", "results_geojson")


def ejecutar_pipeline():
    print("🚀 Iniciando pipeline de detección de deforestación con verificación doble...")

    yolov_detector = DeforestacionDetector()
    imagenes = sorted(glob.glob(os.path.join(CARPETA_IMAGENES, "*.tif")))

    if not imagenes:
        print("⚠️ No se encontraron imágenes .tif en la carpeta:", CARPETA_IMAGENES)
        return

    geojson_paths = []

    for imagen_path in tqdm(imagenes, desc="🔍 Detectando en imágenes .tif"):
        print(f"\n🖼️ Procesando: {os.path.basename(imagen_path)}")
        deteccion_precisa = detectar_con_ambos_modelos_precisa(imagen_path, umbral_iou=0.3)
        if deteccion_precisa:
            geojson_paths.append(deteccion_precisa)

    print("📦 Ejecutando detección en mosaicos (YOLOv11)...")
    meta_geojson = yolov_detector.detect_from_metadata()
    if meta_geojson:
        geojson_paths.append(meta_geojson)

    if not geojson_paths:
        print("❌ No se generó ningún archivo GeoJSON con detecciones.")
        return

    gdfs = [gpd.read_file(path) for path in geojson_paths if os.path.exists(path)]
    if not gdfs:
        print("⚠️ No se pudieron leer los GeoJSON generados.")
        return

    gdf_combined = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), crs=gdfs[0].crs)
    fecha = datetime.now().strftime("%Y-%m-%d")
    geojson_combinado_path = os.path.join(RESULTS_GEOJSON, f"detecciones_{fecha}.geojson")
    gdf_combined.to_file(geojson_combinado_path, driver="GeoJSON")

    print(f"\n🧩 GeoJSON combinado guardado en: {geojson_combinado_path}")
    print(f"📌 Total de detecciones combinadas: {len(gdf_combined)}")

    mostrar_mapa_amazonia_y_detecciones_unico_archivo()


if __name__ == "__main__":
    ejecutar_pipeline()
