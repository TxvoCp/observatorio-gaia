import os
import json
import folium
import geopandas as gpd
from datetime import date
#from osgeo import gdal
import rasterio
from rasterio.transform import Affine
import numpy as np

def image_to_geo_coords(img_coords, transform):
    if isinstance(transform, Affine):
        lon, lat = transform * (img_coords[0], img_coords[1])
        return [lon, lat]
    else:
        x = transform[0] + img_coords[0] * transform[1] + img_coords[1] * transform[2]
        y = transform[3] + img_coords[0] * transform[4] + img_coords[1] * transform[5]
        return [x, y]

def generar_geojson_detecciones(detecciones, imagen_path, output_path):
    try:
        with rasterio.open(imagen_path) as src:
            transform = src.transform


        features = []
        for det in detecciones:
            geo_coords = [image_to_geo_coords(coord, transform) for coord in det['coordenadas']]
            if geo_coords[0] != geo_coords[-1]:
                geo_coords.append(geo_coords[0])
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [geo_coords]
                },
                "properties": det.get('properties', {})
            }
            features.append(feature)

        gdf = gpd.GeoDataFrame.from_features(features)
        gdf.set_crs("EPSG:32720", inplace=True)  
        gdf = gdf.to_crs("EPSG:4326") 

      
        for col in gdf.select_dtypes(include=["datetime64[ns]"]).columns:
            gdf[col] = gdf[col].astype(str)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        gdf.to_file(output_path, driver="GeoJSON")
        return True

    except Exception as e:
        print(f"Error generando GeoJSON: {str(e)}")
        return False

def mostrar_mapa_amazonia_y_detecciones_unico_archivo():
    hoy = date.today().isoformat()
    archivo_detecciones = os.path.join("app", "results_geojson", f"detecciones_{hoy}.geojson")
    archivo_amazonia = os.path.join("app", "data", "amazonia.geojson")
    archivo_biomas_shp = os.path.join("app", "geo", "biomas.shp")

    if not os.path.exists(archivo_amazonia) and os.path.exists(archivo_biomas_shp):
        print("📦 Convirtiendo shapefile de Amazonía a GeoJSON...")
        gdf_amazon = gpd.read_file(archivo_biomas_shp)
        os.makedirs(os.path.dirname(archivo_amazonia), exist_ok=True)
        gdf_amazon.to_file(archivo_amazonia, driver="GeoJSON")
        print("✅ Conversión exitosa.")

    if not os.path.exists(archivo_detecciones):
        print(f"⚠️ El archivo de detecciones no existe: {archivo_detecciones}")
        return False

    try:
        gdf_amazonia = gpd.read_file(archivo_amazonia)
        gdf_detecciones = gpd.read_file(archivo_detecciones)

        if gdf_detecciones.crs != "EPSG:4326":
            gdf_detecciones = gdf_detecciones.to_crs("EPSG:4326")

   
        for col in gdf_detecciones.select_dtypes(include=["datetime64[ns]"]).columns:
            gdf_detecciones[col] = gdf_detecciones[col].astype(str)

        if not gdf_detecciones.empty:
  
            centro = gdf_detecciones.to_crs("EPSG:3857").geometry.centroid.iloc[0]
            centro = gpd.GeoSeries([centro], crs="EPSG:3857").to_crs("EPSG:4326").iloc[0]

            m = folium.Map(
                location=[centro.y, centro.x],
                zoom_start=12,
                tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                attr='Esri World Imagery'
            )
        else:
            m = folium.Map(location=[-3.4653, -62.2159], zoom_start=5)

        folium.GeoJson(
            gdf_amazonia,
            name="Amazonía",
            style_function=lambda feature: {
                "color": "#2ca02c",
                "fillColor": "#2ca02c",
                "fillOpacity": 0.2,
                "weight": 1,
            },
            tooltip=folium.GeoJsonTooltip(fields=["bioma"], aliases=["Bioma:"])
        ).add_to(m)

        if not gdf_detecciones.empty:
            folium.GeoJson(
                gdf_detecciones,
                name="Detecciones de Deforestación",
                style_function=lambda feature: {
                    "fillColor": "#ff0000",
                    "color": "#ff0000",
                    "weight": 2,
                    "fillOpacity": 0.7,
                },
                tooltip=folium.GeoJsonTooltip(
                fields=["modelo", "confidence", "iou", "image", "fecha"],
                aliases=["Modelo:", "Confianza:", "IoU:", "Imagen:", "Fecha:"],
                localize=True
            )


            ).add_to(m)

        folium.LayerControl(collapsed=False).add_to(m)

        output_path = os.path.join("app", "static", "mapa", "mapa.html")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        m.save(output_path)
        print(f"✅ Mapa guardado en {output_path}")
        return True

    except Exception as e:
        print(f"⚠️ Error al generar el mapa: {str(e)}")
        return False
