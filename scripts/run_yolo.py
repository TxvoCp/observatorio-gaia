from ultralytics import YOLO
import os

model = YOLO("models/yolov11.pt")
INPUT_DIR = "tiles/jpg"
OUTPUT_DIR = "runs/detect"

os.makedirs(OUTPUT_DIR, exist_ok=True)

model.predict(
    source=INPUT_DIR,
    save=True,
    save_txt=True,
    project=OUTPUT_DIR,
    name="results",
    imgsz=640,
    conf=0.4
)
