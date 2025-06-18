import os
import json
import numpy as np
from PIL import Image
from datetime import datetime
import warnings

import pandas as pd
import rasterio
from rasterio.transform import xy
import geopandas as gpd
from shapely.geometry import box, Polygon
from app.detection_detectron import Detectron2Detector  
from ultralytics import YOLO

warnings.filterwarnings("ignore", category=UserWarning, module="rasterio")


class DeforestacionDetector:

    
    def __init__(self, model_path="app/models/yolov11_trees.pt"):
        self.model = YOLO(model_path)
        self.meta_file = os.path.join("app", "data", "tile_metadata.json")
        self.results_dir = os.path.join("app", "results")
        self.geojson_dir = os.path.join("app", "results_geojson")
        os.makedirs(self.results_dir, exist_ok=True)
        os.makedirs(self.geojson_dir, exist_ok=True)
        print("✅ Modelo YOLO cargado.")

    def _bbox_to_geo(self, bbox, transform):
        """Convierte un bounding box [x1, y1, x2, y2] a coordenadas geográficas (EPSG:4326)."""
        x1, y1, x2, y2 = bbox
        lon1, lat1 = xy(transform, y1, x1, offset="ul")
        lon2, lat2 = xy(transform, y2, x2, offset="lr")
        return [
            [lon1, lat1],
            [lon2, lat1],
            [lon2, lat2],
            [lon1, lat2],
            [lon1, lat1]  
        ]

    def detect_in_image(self, image_path):
        """Realiza detección sobre una imagen .tif y genera un GeoJSON con detecciones."""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"❌ Imagen no encontrada: {image_path}")

        try:
            results = self.model.predict(
                source=image_path,
                conf=0.5,
                imgsz=640,
                save=True,
                project=self.results_dir,
                name="predict",
                exist_ok=True
            )

            with rasterio.open(image_path) as src:
                transform = src.transform
                crs = src.crs

                features = []
                for result in results:
                    for box_data in result.boxes:
                        bbox = list(map(int, box_data.xyxy[0].tolist()))
                        coords = self._bbox_to_geo(bbox, transform)
                        features.append({
                            "type": "Feature",
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [coords]
                            },
                            "properties": {
                                "confidence": float(box_data.conf),
                                "class_id": int(box_data.cls),
                                "class_name": result.names[int(box_data.cls)],
                                "detection_date": datetime.now().isoformat(),
                                "image_size": f"{result.orig_shape[1]}x{result.orig_shape[0]}"
                            }
                        })

                if not features:
                    print(f"ℹ️ No se detectaron objetos en {os.path.basename(image_path)}")
                    return None

                gdf = gpd.GeoDataFrame.from_features(features, crs=crs).to_crs("EPSG:4326")
                nombre_salida = f"detecciones_{os.path.splitext(os.path.basename(image_path))[0]}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.geojson"
                salida_path = os.path.join(self.geojson_dir, nombre_salida)
                gdf.to_file(salida_path, driver="GeoJSON")

                print(f"✅ GeoJSON guardado: {salida_path}")
                return salida_path

        except Exception as e:
            print(f"❌ Error durante la detección: {e}")
            return None

    def detect_from_metadata(self):
        """Realiza detección usando metadatos de tiles JPG y los transforma a coordenadas geográficas."""
        if not os.path.exists(self.meta_file):
            print("❌ Archivo de metadatos no encontrado.")
            return None

        with open(self.meta_file, "r") as f:
            metadata = json.load(f)

        features = []

        for tile_jpg, info in metadata.items():
            jpg_path = os.path.join("app", "data", tile_jpg)
            if not os.path.exists(jpg_path):
                continue

            results = self.model.predict(source=jpg_path, conf=0.5, imgsz=640)

            for res in results:
                for box in res.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    x1t = info["x_offset"] + x1
                    y1t = info["y_offset"] + y1
                    x2t = info["x_offset"] + x2
                    y2t = info["y_offset"] + y2

                    with rasterio.open(info["tif_path"]) as src:
                        lon1, lat1 = xy(src.transform, int(y2t), int(x1t))
                        lon2, lat2 = xy(src.transform, int(y1t), int(x2t))

                    geom = box(lon1, lat1, lon2, lat2)
                    features.append({
                        "geometry": geom,
                        "properties": {
                            "confidence": float(box.conf),
                            "class_id": int(box.cls),
                            "class_name": res.names[int(box.cls)],
                            "detection_date": datetime.now().isoformat()
                        }
                    })

        if not features:
            print("⚠️ No se detectó deforestación.")
            return None

        gdf = gpd.GeoDataFrame(features, crs="EPSG:4326")
        salida_path = os.path.join(self.geojson_dir, f"detecciones_{datetime.now().strftime('%Y-%m-%d')}.geojson")
        gdf.to_file(salida_path, driver="GeoJSON")
        print(f"✅ GeoJSON generado: {salida_path}")
        return salida_path

    
def detect_and_geolocate():
    detector = DeforestacionDetector()
    return detector.detect_from_metadata()

def detectar_con_ambos_modelos(imagen_path):
        yolov_detector = DeforestacionDetector()
        detectron2_detector = Detectron2Detector()

        print("🔍 Detectando con YOLOv11...")
        yolov_geojson = yolov_detector.detect_in_image(imagen_path)

        print("🔍 Detectando con Detectron2...")
        detectron2_geojson = detectron2_detector.detect(imagen_path)

        if not yolov_geojson and not detectron2_geojson:
            print("❌ Ningún modelo detectó deforestación.")
            return None


        if yolov_geojson and detectron2_geojson:
            combined_gdf = gpd.read_file(yolov_geojson)
            gdf2 = gpd.read_file(detectron2_geojson)
            combined_gdf = gpd.GeoDataFrame(pd.concat([combined_gdf, gdf2], ignore_index=True), crs="EPSG:4326")
            
            output_path = os.path.join("app", "results_geojson", f"detecciones_combinadas_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.geojson")
            combined_gdf.to_file(output_path, driver="GeoJSON")
            print(f"✅ GeoJSON combinado guardado: {output_path}")
            return output_path

        return yolov_geojson or detectron2_geojson
