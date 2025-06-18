import os
import json
import rasterio
from rasterio.transform import Affine

LABELS_DIR = "runs/detect/results/labels"
TIF_DIR = "tiles/tif"
OUTPUT_GEOJSON = "detections/geojson/detecciones.geojson"

features = []

for txt_file in os.listdir(LABELS_DIR):
    if txt_file.endswith(".txt"):
        name = txt_file.replace(".txt", "")
        tif_path = os.path.join(TIF_DIR, name + ".tif")
        label_path = os.path.join(LABELS_DIR, txt_file)

        with rasterio.open(tif_path) as src:
            transform: Affine = src.transform

            with open(label_path, "r") as f:
                for line in f:
                    parts = line.strip().split()
                    class_id, x_center, y_center, w, h = map(float, parts)
                    col = int(x_center * src.width)
                    row = int(y_center * src.height)
                    lon, lat = transform * (col, row)
                    
                    features.append({
                        "type": "Feature",
                        "properties": {
                            "class_id": int(class_id),
                            "tile": name
                        },
                        "geometry": {
                            "type": "Point",
                            "coordinates": [lon, lat]
                        }
                    })

geojson = {
    "type": "FeatureCollection",
    "features": features
}

os.makedirs(os.path.dirname(OUTPUT_GEOJSON), exist_ok=True)
with open(OUTPUT_GEOJSON, "w") as f:
    json.dump(geojson, f, indent=2)

print(f"GeoJSON generado en: {OUTPUT_GEOJSON}")
