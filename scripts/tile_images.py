import os
import rasterio
from rasterio.windows import Window
from PIL import Image
import numpy as np

INPUT_DIR = "data/amazonia"
OUTPUT_TIF = "tiles/tif"
OUTPUT_JPG = "tiles/jpg"
TILE_SIZE = 640

os.makedirs(OUTPUT_TIF, exist_ok=True)
os.makedirs(OUTPUT_JPG, exist_ok=True)

for file in os.listdir(INPUT_DIR):
    if file.endswith(".tif"):
        path = os.path.join(INPUT_DIR, file)
        with rasterio.open(path) as src:
            width, height = src.width, src.height
            for i in range(0, height, TILE_SIZE):
                for j in range(0, width, TILE_SIZE):
                    window = Window(j, i, TILE_SIZE, TILE_SIZE)
                    transform = src.window_transform(window)
                    tile = src.read(window=window)
                    tile_tif_path = os.path.join(OUTPUT_TIF, f"{file[:-4]}_{i}_{j}.tif")
                    tile_jpg_path = os.path.join(OUTPUT_JPG, f"{file[:-4]}_{i}_{j}.jpg")

                    profile = src.profile
                    profile.update({
                        "height": TILE_SIZE,
                        "width": TILE_SIZE,
                        "transform": transform
                    })
                    with rasterio.open(tile_tif_path, "w", **profile) as dst:
                        dst.write(tile)

                    img = np.moveaxis(tile, 0, -1)
                    if img.shape[-1] == 1:
                        img = img[:, :, 0]
                    img = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
                    img.save(tile_jpg_path)
