import os
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware

from google.cloud import firestore
from dotenv import load_dotenv
import asyncio
from typing import List, Dict, Any

load_dotenv()

credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if not credentials_path:
    raise Exception("GOOGLE_APPLICATION_CREDENTIALS no está definido en las variables de entorno.")

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path


db = firestore.Client()

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


async def resolve_document_reference(ref: firestore.DocumentReference, resolved_refs: set = None) -> Dict[str, Any]:
    if resolved_refs is None:
        resolved_refs = set()

    if str(ref.path) in resolved_refs:
        return {"id": ref.id, "path": str(ref.path), "error": "Referencia circular detectada"}

    resolved_refs.add(str(ref.path))

    try:
        doc = ref.get()
        if doc.exists:
            doc_data = doc.to_dict()
            resolved_doc = {}
            for key, value in doc_data.items():
                if isinstance(value, firestore.DocumentReference):
                    resolved_doc[key] = await resolve_document_reference(value, resolved_refs)
                elif isinstance(value, list):
                    resolved_list = []
                    for item in value:
                        if isinstance(item, firestore.DocumentReference):
                            resolved_list.append(await resolve_document_reference(item, resolved_refs))
                        else:
                            resolved_list.append(item)
                    resolved_doc[key] = resolved_list
                else:
                    resolved_doc[key] = value

            return {"id": doc.id, **resolved_doc}
        else:
            return {"error": "Documento no encontrado", "path": str(ref.path)}
    except Exception as e:
        return {"error": str(e), "path": str(ref.path)}


def make_serializable(data: Dict[str, Any]) -> Dict[str, Any]:
    serializable_data = {}
    for key, value in data.items():
        if isinstance(value, firestore.DocumentReference):
            serializable_data[key] = value
        elif isinstance(value, (list, dict, str, int, float, type(None))):
            serializable_data[key] = value
        else:
            serializable_data[key] = str(value)
    return serializable_data


@app.get("/get-user-info")
async def get_user_info(user_id: str):
    collection_ref = db.collection("users").where("user_id", "==", user_id)
    docs = collection_ref.stream()

    data = []
    for doc in docs:
        raw_data = doc.to_dict()
        serializable_data = make_serializable(raw_data)

        resolved_data = {}
        for key, value in serializable_data.items():
            if isinstance(value, firestore.DocumentReference):
                resolved_data[key] = await resolve_document_reference(value)
            else:
                resolved_data[key] = value

        data.append({"id": doc.id, **resolved_data})

    if not data:
        raise HTTPException(status_code=404, detail="No se encontraron datos para el usuario especificado")

    return {"user_info": data[0]}

@app.post("/create-user")
async def create_user(user_data: dict = Body(...)):
    try:
        role_id = user_data.get("role_id")
        if not role_id:
            raise HTTPException(status_code=400, detail="role_id es requerido")

        role_ref = db.collection("roles").document(role_id)
        role_doc = role_ref.get()

        if not role_doc.exists:
            raise HTTPException(status_code=404, detail=f"Role con id {role_id} no encontrado")

        user_data["role"] = role_ref

        user_data.pop("role_id", None)

        organization_name = user_data.get("organization_name")
        organization_ref = None
        if organization_name:
            organization_ref = db.collection("organizations").document()
            organization_ref.set({"name": organization_name})

            user_data["organization"] = organization_ref

            user_data.pop("organization_name", None)

        collection_ref = db.collection("users")

        doc_ref = collection_ref.add(user_data)

        doc_id = doc_ref[1].id

        if organization_ref:
            organization_ref.update({"admin_id": doc_ref[1]})

        return {"message": "Usuario creado exitosamente", "user_id": doc_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear el usuario: {e}")

@app.get("/get-roles")
async def get_roles():
    collection_ref = db.collection("roles")
    docs = collection_ref.stream()

    data = []
    for doc in docs:
        raw_data = doc.to_dict()
        serializable_data = make_serializable(raw_data)

        for key, value in serializable_data.items():
            if isinstance(value, firestore.DocumentReference):
                serializable_data[key] = await resolve_document_reference(value)

        data.append({"id": doc.id, **serializable_data})

    if not data:
        raise HTTPException(status_code=404, detail="No se encontraron datos para el usuario especificado")

    return {"roles": data}
@app.get("/get-products")
async def get_products(country: str):
    collection_ref = db.collection("maps_data").where("country", "==", country)
    docs = collection_ref.stream()

    data = []

    async def fetch_data(doc):
        data.append({"id": doc.id, **doc.to_dict()})

    tasks = [fetch_data(doc) for doc in docs]
    await asyncio.gather(*tasks)

    if not data:
        raise HTTPException(status_code=404, detail="No se encontraron datos para la ciudad especificada")

    return {"products": data}

@app.get("/distributor-data")
async def get_distributor_data(country: str, distributor_type: str):
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

    return {
        "routes": routes
    }

@app.get("/distribution-zones")
async def get_distribution_zones(country: str):
    collection_ref = db.collection("maps_data").where("country", "==", country)
    docs = collection_ref.stream()

    zones = {}

    async def process_doc(doc):
        doc_data = doc.to_dict()
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
                "points": [],
                "point_data": []
            }

        zones[zone_key]["sales_summary"]["total_units"] += doc_data["sales_units"]
        zones[zone_key]["sales_summary"]["total_liters"] += doc_data["sales_liters"]
        zones[zone_key]["sales_summary"]["total_usd"] += doc_data["sales_usd"]

        zones[zone_key]["points"].append(doc_data["gps_coordinates"])

        zones[zone_key]["point_data"].append({
            "gps_coordinates": doc_data["gps_coordinates"],
            "sales_units": doc_data["sales_units"],
            "sales_liters": doc_data["sales_liters"],
            "sales_usd": doc_data["sales_usd"],
        })

    tasks = [process_doc(doc) for doc in docs]
    await asyncio.gather(*tasks)

    if not zones:
        raise HTTPException(status_code=404, detail="No se encontraron datos para el país especificado")

    return {"zones": list(zones.values())}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
