import os
import geopandas as gpd
from shapely.geometry import box
from datetime import date, timedelta
from pystac_client import Client
from planetary_computer import sign
import rasterio
from rasterio.merge import merge
import warnings
warnings.filterwarnings("ignore")
from PIL import Image
import numpy as np
from matplotlib import pyplot as plt

tile_metadata = {} 

def descargar_imagenes_bioma_amazonico():
    print("📍 Leyendo archivo de biomas...")
    gdf = gpd.read_file("app/geo/biomas.shp")
    if gdf.crs is None:
        gdf.set_crs(epsg=4326, inplace=True)
    gdf = gdf.to_crs(epsg=4326)
    geom_total = gdf.unary_union.simplify(0.01, preserve_topology=True)
    
    print("🌍 Configurando intervalo de fechas...")
    hoy = date.today()
    hace_16_dias = hoy - timedelta(days=16)
    time_range = f"{hace_16_dias}/{hoy}"

    print("🔍 Abriendo catálogo STAC...")
    catalog = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")
    
    query = {
        "eo:cloud_cover": {"lt": 15},
        "platform": {"in": ["landsat-8", "landsat-9"]},
        "view:sun_elevation": {"gt": 10}
    }

    print("🔄 Realizando búsqueda de imágenes...")
    search = catalog.search(
        collections=["landsat-c2-l2"],
        intersects=geom_total.__geo_interface__,
        datetime=time_range,
        query=query,
        limit=100
    )

    items = list(search.get_items())
    if not items:
        print("❌ No se encontraron imágenes Landsat recientes.")
        return

    print(f"🔍 Se encontraron {len(items)} imágenes Landsat.")
    os.makedirs("app/data", exist_ok=True)

    for item in items:
        item = sign(item)
        img_id = item.id
        output_path = os.path.join("app/data", f"{img_id}_RGB.tif")
        if os.path.exists(output_path):
            print(f"✅ Ya existe: {output_path}")
            continue

        try:
            with rasterio.open(item.assets["red"].href) as red:
                red_data = red.read(1)
                profile = red.profile

            with rasterio.open(item.assets["green"].href) as green:
                green_data = green.read(1)

            with rasterio.open(item.assets["blue"].href) as blue:
                blue_data = blue.read(1)

            rgb = np.stack([red_data, green_data, blue_data])
            rgb = normalizar_bandas(rgb)

            profile.update(count=3, dtype='uint8')

            with rasterio.open(output_path, "w", **profile) as dst:
                dst.write(rgb[0], 1)
                dst.write(rgb[1], 2)
                dst.write(rgb[2], 3)

            print(f"✅ Imagen guardada en: {output_path}")
            cortar_y_convertir_a_jpg(output_path)

        except Exception as e:
            print(f"⚠️ Error procesando {img_id}: {e}")

    unir_mosaicos()

def unir_mosaicos():
    import tempfile
    from rasterio.warp import calculate_default_transform, reproject, Resampling
    from rasterio.merge import merge

    INPUT_DIR = "app/data"
    OUTPUT_PATH = os.path.join(INPUT_DIR, "mosaico_RGB.tif")
    CRS_OBJETIVO = "EPSG:4326"
    RESOLUCION_EN_GRADOS = 0.005 

    def dividir_lista(lista, tamano):
        for i in range(0, len(lista), tamano):
            yield lista[i:i + tamano]

    def reproyectar_tifs(input_dir, output_crs):
        temp_dir = tempfile.mkdtemp()
        reproyectadas = []

        tifs = [f for f in os.listdir(input_dir) if f.endswith(".tif") and "mosaico" not in f and "sub_mosaico" not in f]

        for tif in tifs:
            path = os.path.join(input_dir, tif)

            with rasterio.open(path) as src:
                transform, width, height = calculate_default_transform(
                    src.crs, output_crs, src.width, src.height, *src.bounds, resolution=RESOLUCION_EN_GRADOS
                )

                kwargs = src.meta.copy()
                kwargs.update({
                    'crs': output_crs,
                    'transform': transform,
                    'width': width,
                    'height': height
                })

                reproj_path = os.path.join(temp_dir, f"repro_{tif}")
                with rasterio.open(reproj_path, 'w', **kwargs) as dst:
                    for i in range(1, src.count + 1):
                        reproject(
                            source=rasterio.band(src, i),
                            destination=rasterio.band(dst, i),
                            src_transform=src.transform,
                            src_crs=src.crs,
                            dst_transform=transform,
                            dst_crs=output_crs,
                            resampling=Resampling.nearest
                        )
                reproyectadas.append(reproj_path)
                print(f"🔄 Reproyectado: {tif}")

        return reproyectadas

    def unir_mosaico(tifs_reproyectados, output_path):
        if not tifs_reproyectados:
            print("⚠️ No hay imágenes reproyectadas para unir.")
            return

        print(f"🧩 Uniendo {len(tifs_reproyectados)} imágenes...")
        src_files_to_mosaic = [rasterio.open(p) for p in tifs_reproyectados]

        mosaic, out_transform = merge(src_files_to_mosaic, method='first')

        out_meta = src_files_to_mosaic[0].meta.copy()
        out_meta.update({
            "driver": "GTiff",
            "height": mosaic.shape[1],
            "width": mosaic.shape[2],
            "transform": out_transform,
            "count": mosaic.shape[0],
            "dtype": mosaic.dtype
        })

        with rasterio.open(output_path, "w", **out_meta) as dest:
            dest.write(mosaic)

        print(f"✅ Guardado: {output_path}")

    print("🔧 Iniciando mosaico progresivo...")
    reproyectadas = reproyectar_tifs(INPUT_DIR, CRS_OBJETIVO)

    sub_mosaicos = []
    for idx, grupo in enumerate(dividir_lista(reproyectadas, 2)):
        sub_path = os.path.join(INPUT_DIR, f"sub_mosaico_{idx}.tif")
        unir_mosaico(grupo, output_path=sub_path)
        sub_mosaicos.append(sub_path)

    unir_mosaico(sub_mosaicos, output_path=OUTPUT_PATH)

    print("🏁 Mosaico final generado correctamente.")

 
    for path in os.listdir(INPUT_DIR):
        if path.endswith(".tif") and "mosaico" not in path:
            try:
                os.remove(os.path.join(INPUT_DIR, path))
                print(f"🗑️ Eliminado: {path}")
            except Exception as e:
                print(f"⚠️ No se pudo eliminar {path}: {e}")

def cortar_y_convertir_a_jpg(tif_path, salida_dir="app/data"):
    try:
        with rasterio.open(tif_path) as src:
            img_array = src.read()
            img_array = np.transpose(img_array, (1, 2, 0))

        img_array = img_array.astype(np.float32)

        for i in range(3):
            canal = img_array[:, :, i]
            if i == 1:
                p2, p98 = np.percentile(canal, 1), np.percentile(canal, 99.5)
                canal = np.clip(canal, p2, p98)
                canal = ((canal - p2) / (p98 - p2)) * 255.0
                canal *= 1.3
            else:
                p2, p98 = np.percentile(canal, 2), np.percentile(canal, 98)
                canal = np.clip(canal, p2, p98)
                canal = ((canal - p2) / (p98 - p2)) * 255.0
            canal = np.clip(canal, 0, 255)
            img_array[:, :, i] = canal

        height, width, _ = img_array.shape
        tile_size = 640
        count = 0

        for y in range(0, height, tile_size):
            for x in range(0, width, tile_size):
                if y + tile_size <= height and x + tile_size <= width:
                    tile = img_array[y:y + tile_size, x:x + tile_size, :]
                    dark_ratio = np.mean(tile < 15)
                    if dark_ratio > 0.8 or tile.mean() < 20:
                        continue

                    tile = tile.astype(np.uint8)
                    img = Image.fromarray(tile)
                    tile_name = os.path.basename(tif_path).replace(".tif", f"_tile_{y//tile_size}_{x//tile_size}.jpg")
                    img.save(os.path.join(salida_dir, tile_name), quality=95)
                    count += 1

        print(f"🧩 {count} tiles JPG útiles generados desde: {tif_path}")
    except Exception as e:
        print(f"⚠️ Error al cortar y convertir: {e}")

def normalizar_bandas(rgb_array):
    rgb_array = rgb_array.astype(np.float32)
    for i in range(3):
        canal = rgb_array[i, :, :]
        p2 = np.percentile(canal, 2)
        p98 = np.percentile(canal, 98)
        canal = np.clip(canal, p2, p98)
        canal = ((canal - p2) / (p98 - p2)) * 255.0
        rgb_array[i, :, :] = canal
    return rgb_array.astype(np.uint8)
