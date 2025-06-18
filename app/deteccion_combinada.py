import os
import geopandas as gpd
from datetime import datetime

from app.detection import DeforestacionDetector
from app.detection_detectron import Detectron2Detector


def detectar_con_ambos_modelos_precisa(imagen_path, umbral_iou=0.3):
    yolov_detector = DeforestacionDetector()
    detectron2_detector = Detectron2Detector()

    print("🔍 Detectando con YOLOv11...")
    yolov_geojson = yolov_detector.detect_in_image(imagen_path)

    print("🔍 Detectando con Detectron2...")
    detectron2_geojson = detectron2_detector.detect(imagen_path)

    if not yolov_geojson and not detectron2_geojson:
        print("⚠️ Ninguno de los modelos detectó algo.")
        return None

    detecciones = []

    if yolov_geojson:
        gdf_yolo = gpd.read_file(yolov_geojson)
        for _, row in gdf_yolo.iterrows():
            detecciones.append({
                "geometry": row.geometry,
                "properties": {
                    "modelo": "YOLOv11",
                    "confidence": row.get("confidence", 0),
                    "image": os.path.basename(imagen_path),
                    "fecha": datetime.now().isoformat()
                }
            })

    if detectron2_geojson and yolov_geojson:
        gdf_detectron = gpd.read_file(detectron2_geojson)
        for _, row_d in gdf_detectron.iterrows():
            poly_d = row_d.geometry
            for _, row_y in gdf_yolo.iterrows():
                poly_y = row_y.geometry
                if poly_y.intersects(poly_d):
                    inter = poly_y.intersection(poly_d)
                    union = poly_y.union(poly_d)
                    iou = inter.area / union.area if union.area != 0 else 0
                    if iou >= umbral_iou:
                        detecciones.append({
                            "geometry": inter,
                            "properties": {
                                "modelo": "Detectron2",
                                "confidence": row_d.get("confidence", 0),
                                "iou": iou,
                                "image": os.path.basename(imagen_path),
                                "fecha": datetime.now().isoformat()
                            }
                        })
                    break

    if not detecciones:
        print("⚠️ No se confirmó ninguna detección.")
        return None

    gdf_final = gpd.GeoDataFrame.from_features(detecciones, crs="EPSG:4326")
    salida_path = os.path.join("app", "results_geojson", f"detecciones_confirmadas_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.geojson")
    gdf_final.to_file(salida_path, driver="GeoJSON")

    print(f"✅ GeoJSON de detecciones guardado: {salida_path}")
    return salida_path
