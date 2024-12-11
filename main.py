import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google.cloud import firestore
from dotenv import load_dotenv
import asyncio
from typing import List, Dict, Any
import numpy as np
from scipy.spatial import ConvexHull

# Cargar las variables de entorno desde un archivo .env
load_dotenv()

# Configurar la ruta al archivo JSON de claves de servicio
credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if not credentials_path:
    raise Exception("GOOGLE_APPLICATION_CREDENTIALS no está definido en las variables de entorno.")

# Asegurarse de que la variable esté disponible para las bibliotecas de Google
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path

# Inicializar Firestore
db = firestore.Client()

# Crear una instancia de la aplicación FastAPI
app = FastAPI()

origins = [
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Ruta para obtener información desde Firestore
@app.get("/maps_data")
async def get_maps_information(country: str):
    collection_ref = db.collection("maps_data").where("country", "==", country)
    docs = collection_ref.stream()

    data = []

    async def fetch_data(doc):
        data.append({"id": doc.id, **doc.to_dict()})

    tasks = [fetch_data(doc) for doc in docs]
    await asyncio.gather(*tasks)

    if not data:
        raise HTTPException(status_code=404, detail="No se encontraron datos para la ciudad especificada")

    return {"maps_data": data}

@app.get("/distributor_data")
async def get_distributor_data(country: str, distributor_type: str):
    # Filtra por country y distributor_type
    collection_ref = (
        db.collection("maps_data")
        .where("country", "==", country)
        .where("distributor_type", "==", distributor_type)
    )
    docs = collection_ref.stream()

    data = []

    async def fetch_data(doc):
        data.append({"id": doc.id, **doc.to_dict()})

    tasks = [fetch_data(doc) for doc in docs]
    await asyncio.gather(*tasks)

    if not data:
        raise HTTPException(status_code=404, detail="No se encontraron datos para los filtros especificados")

    return {"distributors": data}

@app.get("/countries")
async def get_countries():
    collection_ref = db.collection("maps_data")
    docs = collection_ref.stream()

    countries = set()

    async def fetch_country(doc):
        doc_data = doc.to_dict()
        if 'country' in doc_data:
            countries.add(doc_data['country'])

    tasks = [fetch_country(doc) for doc in docs]
    await asyncio.gather(*tasks)

    if not countries:
        raise HTTPException(status_code=404, detail="No se encontraron datos para los países")

    return {"countries": list(countries)}

@app.get("/routes-by-country")
async def get_routes(country: str):
    collection_ref = db.collection("maps_data").where("country", "==", country)
    docs = collection_ref.stream()

    routes = set()

    async def fetch_data(doc):
        doc_data = doc.to_dict()
        if 'route' in doc_data:
            routes.add(doc_data['route'])

    tasks = [fetch_data(doc) for doc in docs]
    await asyncio.gather(*tasks)

    if not routes and not routes:
        raise HTTPException(status_code=404, detail="No se encontraron datos para las rutas")

    print(f'routess {routes}')

    return {
        "routes": routes
    }

@app.get("/distribution_zones")
async def get_distribution_zones(country: str):
    # Colección base de Firestore
    collection_ref = db.collection("maps_data").where("country", "==", country)
    docs = collection_ref.stream()

    # Almacenar los datos en un diccionario agrupado
    zones = {}

    async def process_doc(doc):
        doc_data = doc.to_dict()
        # Define la clave de agrupamiento, por ejemplo, "city" + "route"
        zone_key = f"{doc_data['city']}-{doc_data['route']}"
        if zone_key not in zones:
            zones[zone_key] = {
                "city": doc_data["city"],
                "route": doc_data["route"],
                "isocrona": doc_data.get("isocrona", "Unknown"),
                "sales_summary": {
                    "total_units": 0,
                    "total_liters": 0,
                    "total_usd": 0.0,
                },
                "points": [],  # Lista para almacenar puntos GPS
            }

        # Sumar los datos de ventas
        zones[zone_key]["sales_summary"]["total_units"] += doc_data["sales_units"]
        zones[zone_key]["sales_summary"]["total_liters"] += doc_data["sales_liters"]
        zones[zone_key]["sales_summary"]["total_usd"] += doc_data["sales_usd"]

        # Agregar las coordenadas del punto
        zones[zone_key]["points"].append(doc_data["gps_coordinates"])

    # Procesar documentos en paralelo
    tasks = [process_doc(doc) for doc in docs]
    await asyncio.gather(*tasks)

    if not zones:
        raise HTTPException(status_code=404, detail="No se encontraron datos para el país especificado")

    # Convertir el resultado a una lista
    return {"zones": list(zones.values())}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
