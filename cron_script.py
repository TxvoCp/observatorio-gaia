import os
from app.download_landsat import descargar_imagenes_bioma_amazonico, unir_mosaicos
from app.detection import DeforestacionDetector
from datetime import date

def ejecutar_tarea_programada():
    print("[CRON] Iniciando descarga de imágenes Landsat...")
    descargar_imagenes_bioma_amazonico()

    print("[CRON] Uniendo mosaicos RGB...")
    unir_mosaicos()

    print("[CRON] Procesando mosaico con YOLOv11...")
    mosaico_path = os.path.join("app/data", "mosaico_RGB.tif")
    if os.path.exists(mosaico_path):
        detecciones = DeforestacionDetector(mosaico_path, modelo="YOLOv11")
        print("✅ Procesado y guardado el mosaico.")
    else:
        print("❌ No se encontró el mosaico para procesar.")

    print("[CRON] Proceso completo. Detecciones guardadas en app/results_geojson/")

if __name__ == "__main__":
    ejecutar_tarea_programada()
