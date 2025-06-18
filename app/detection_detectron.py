import torch
import os
import numpy as np
from datetime import datetime
from detectron2.engine import DefaultPredictor
from detectron2.config import get_cfg
from detectron2 import model_zoo
from detectron2.structures import Boxes
from detectron2.utils.visualizer import Visualizer
import geopandas as gpd
from shapely.geometry import Polygon
import rasterio
from rasterio.transform import xy


class Detectron2Detector:
    def __init__(self, model_path="app/models/detectron2.pth"):
        cfg = get_cfg()
        cfg.merge_from_file(model_zoo.get_config_file(
            "COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x.yaml"))
        cfg.MODEL.ROI_HEADS.NUM_CLASSES = 1  # Ajusta según tus clases
        cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.5
        cfg.MODEL.WEIGHTS = model_path
        cfg.MODEL.DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
        self.predictor = DefaultPredictor(cfg)
        print("✅ Modelo Detectron2 cargado.")

    def detect(self, image_path):
        with rasterio.open(image_path) as src:
            img = src.read([1, 2, 3]).transpose(1, 2, 0)
            transform = src.transform
            crs = src.crs

        outputs = self.predictor(img)
        instances = outputs["instances"].to("cpu")

        features = []
        for i in range(len(instances)):
            box = instances.pred_boxes[i].tensor.numpy().flatten()
            x1, y1, x2, y2 = box
            coords = self._bbox_to_geo([x1, y1, x2, y2], transform)
            polygon = Polygon(coords)

            features.append({
                "geometry": polygon,
                "properties": {
                    "confidence": float(instances.scores[i]),
                    "class_id": int(instances.pred_classes[i]),
                    "detection_model": "detectron2",
                    "detection_date": datetime.now().isoformat()
                }
            })

        if not features:
            print("⚠️ No se detectó deforestación con Detectron2.")
            return None

        gdf = gpd.GeoDataFrame(features, crs=crs).to_crs("EPSG:4326")
        output_path = os.path.join("app", "results_geojson", f"detecciones_detectron2_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.geojson")
        gdf.to_file(output_path, driver="GeoJSON")
        print(f"✅ GeoJSON Detectron2 guardado: {output_path}")
        return output_path

    def _bbox_to_geo(self, bbox, transform):
        x1, y1, x2, y2 = bbox
        lon1, lat1 = xy(transform, y1, x1, offset="ul")
        lon2, lat2 = xy(transform, y2, x2, offset="lr")
        return [
            (lon1, lat1),
            (lon2, lat1),
            (lon2, lat2),
            (lon1, lat2),
            (lon1, lat1)
        ]
