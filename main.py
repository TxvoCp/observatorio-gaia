from flask import Flask, jsonify, render_template, request, redirect, url_for
from app.download_landsat import descargar_imagenes_bioma_amazonico
from app.detection import DeforestacionDetector, detect_and_geolocate
from app.geojson_utils import mostrar_mapa_amazonia_y_detecciones_unico_archivo
#from app.detection import detectar_con_ambos_modelos
import os
import sys
import shutil

# Inicio
if "--clear-data" in sys.argv:
    shutil.rmtree("app/data", ignore_errors=True)
    shutil.rmtree("app/results_geojson", ignore_errors=True)
    print("🧹 Carpetas de datos eliminadas")

app = Flask(__name__,
            static_folder=os.path.join("app", "static"),
            template_folder=os.path.join("app", "templates"))

@app.route('/')
def index():
    return redirect(url_for('static', filename='mapa/mapa.html'))


@app.route('/descargar_imagen')
def descargar():
    path = descargar_imagenes_bioma_amazonico()
    return f"✅ Imagen Landsat descargada en: {path}" if path else "❌ Error al descargar imagen"

@app.route('/mapa')
def mostrar_mapa():
    if mostrar_mapa_amazonia_y_detecciones_unico_archivo():
        return redirect(url_for('static', filename='mapa/mapa.html'))
    return "❌ Error al generar el mapa", 500

"""
@app.route('/detectar_arbol', methods=['POST'])
def detectar_arbol():
    data = request.get_json()
    imagen_path = data.get("imagen_path")

    if not imagen_path or not os.path.exists(imagen_path):
        return jsonify({"error": "Ruta de imagen no válida"}), 400

    try:
        resultado = detectar_arboles_en_imagen(imagen_path)
        if resultado:
            return jsonify({
                "mensaje": "Detección completada",
                "resultado_path": resultado,
                "mapa_url": url_for('mostrar_mapa')
            })
        return jsonify({"error": "No se detectaron áreas de deforestación"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
"""
@app.route('/proceso_completo')
def proceso():
    descargar_imagenes_bioma_amazonico()
    geojson_path = detect_and_geolocate()
    if geojson_path:
        mostrar_mapa_amazonia_y_detecciones_unico_archivo()
        return redirect(url_for('static', filename='mapa/mapa.html'))
    return "❌ No se pudo completar el proceso", 500

@app.route('/regenerar_mapa')
def regenerar_mapa():
    shutil.rmtree("app/static/mapa", ignore_errors=True)
    os.makedirs("app/static/mapa", exist_ok=True)
    if mostrar_mapa_amazonia_y_detecciones_unico_archivo():
        return "✅ Mapa regenerado"
    return "❌ Error al regenerar mapa"

@app.route('/api/geojsons')
def listar_geojsons():
    geojson_dir = os.path.join("app", "results_geojson")
    geojsons = []
    
    for filename in os.listdir(geojson_dir):
        if filename.endswith(".geojson"):
            path = os.path.join(geojson_dir, filename)
            with open(path, "r", encoding="utf-8") as f:
                geojsons.append({
                    "filename": filename,
                    "data": f.read()
                })

    return jsonify(geojsons)


#def detectar_arboles_en_imagen(imagen_path):
#   return detectar_con_ambos_modelos(imagen_path)


if __name__ == '__main__':

    os.makedirs(os.path.join("app", "results_geojson"), exist_ok=True)
    os.makedirs(os.path.join("app", "static", "mapa"), exist_ok=True)
    
    app.run(debug=True, host='0.0.0.0', port=5000)