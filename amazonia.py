import os
import requests

# Países que contienen parte de la Amazonía (códigos ISO Alpha-3 y nombres comunes)
amazonian_countries = {
    "BRA": "Brazil",
    "BOL": "Bolivia",
    "PER": "Peru",
    "ECU": "Ecuador",
    "COL": "Colombia",
    "VEN": "Venezuela",
    "GUY": "Guyana",
    "SUR": "Suriname",
    "GUF": "French Guiana"
}

# URL base del repositorio world.geo.json
base_url = "https://raw.githubusercontent.com/johan/world.geo.json/master/countries/"

# Carpeta de salida
output_dir = "geojson_amazonia"
os.makedirs(output_dir, exist_ok=True)

# Descarga uno por uno
for iso_code, country_name in amazonian_countries.items():
    filename = f"{iso_code}.geo.json"
    url = f"{base_url}{filename}"
    print(f"Descargando {country_name} desde {url} ...")

    response = requests.get(url)
    if response.status_code == 200:
        output_path = os.path.join(output_dir, f"{country_name}.geo.json")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(response.text)
        print(f"✔ Guardado: {output_path}")
    else:
        print(f"❌ Error al descargar {country_name}: {response.status_code}")
