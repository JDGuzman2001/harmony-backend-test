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


@app.get("/get-organization-info")
async def get_organization_info(organization_id: str):
    organization_ref = db.collection("organizations").document(organization_id)

    org_doc = organization_ref.get()

    if not org_doc.exists:
        raise HTTPException(status_code=404, detail="Organización no encontrada")

    org_data = org_doc.to_dict()
    serializable_org_data = make_serializable(org_data)

    resolved_org_data = {}
    for key, value in serializable_org_data.items():
        if isinstance(value, firestore.DocumentReference):
            resolved_org_data[key] = await resolve_document_reference(value)
        else:
            resolved_org_data[key] = value

    departments_ref = db.collection("departments").where("organization", "==", organization_ref)
    departments_docs = departments_ref.stream()

    departments_data = []
    for dept_doc in departments_docs:
        dept_dict = dept_doc.to_dict()
        serializable_dept_data = make_serializable(dept_dict)

        resolved_dept_data = {}
        for key, value in serializable_dept_data.items():
            if isinstance(value, firestore.DocumentReference):
                resolved_dept_data[key] = await resolve_document_reference(value)
            else:
                resolved_dept_data[key] = value

        departments_data.append({"id": dept_doc.id, **resolved_dept_data})

    users_ref = db.collection("users").where("organization", "==", organization_ref)
    users_docs = users_ref.stream()

    users_data = []
    for user_doc in users_docs:
        user_dict = user_doc.to_dict()
        serializable_user_data = make_serializable(user_dict)

        resolved_user_data = {}
        for key, value in serializable_user_data.items():
            if isinstance(value, firestore.DocumentReference):
                resolved_user_data[key] = await resolve_document_reference(value)
            else:
                resolved_user_data[key] = value

        users_data.append({"id": user_doc.id, **resolved_user_data})

    response_data = {
        "organization": {"id": organization_id, **resolved_org_data},
        "departments": departments_data,
        "users": users_data
    }

    if not departments_data and not users_data:
        raise HTTPException(status_code=404,
                            detail="No se encontraron departamentos ni usuarios para la organización especificada")

    return {
        'organization': response_data
    }

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

@app.post("/create-task")
async def create_task(task_data: dict = Body(...)):
    try:
        assigned_to_id = task_data.get("assigned_to_id")
        created_by_id = task_data.get("created_by_id")
        department_id = task_data.get("department_id")
        organization_id = task_data.get("organization_id")
        expected_outcome = task_data.get("expected_outcome")
        status = task_data.get("status")
        title = task_data.get("title")

        if not all([assigned_to_id, created_by_id, department_id, organization_id, expected_outcome, status, title]):
            raise HTTPException(status_code=400, detail="Todos los campos son requeridos")

        assigned_to_ref = db.collection("users").document(assigned_to_id)
        created_by_ref = db.collection("users").document(created_by_id)
        department_ref = db.collection("departments").document(department_id)
        organization_ref = db.collection("organizations").document(organization_id)

        if not assigned_to_ref.get().exists:
            raise HTTPException(status_code=404, detail=f"Usuario asignado con id {assigned_to_id} no encontrado")

        if not created_by_ref.get().exists:
            raise HTTPException(status_code=404, detail=f"Usuario creador con id {created_by_id} no encontrado")

        if not department_ref.get().exists:
            raise HTTPException(status_code=404, detail=f"Departamento con id {department_id} no encontrado")

        if not organization_ref.get().exists:
            raise HTTPException(status_code=404, detail=f"Organización con id {organization_id} no encontrada")

        task_data = {
            "assigned_to": assigned_to_ref,
            "created_by": created_by_ref,
            "department": department_ref,
            "organization": organization_ref,
            "expected_outcome": expected_outcome,
            "status": status,
            "title": title,
        }

        task_ref = db.collection("tasks").add(task_data)

        return {"message": "Tarea creada exitosamente", "task_id": task_ref[1].id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear la tarea: {e}")

@app.put("/update-task")
async def update_task(task_id: str, task_data: dict = Body(...)):
    try:
        task_ref = db.collection("tasks").document(task_id)
        if not task_ref.get().exists:
            raise HTTPException(status_code=404, detail=f"Tarea con id {task_id} no encontrada")

        updated_fields = {}
        if "assigned_to_id" in task_data:
            assigned_to_ref = db.collection("users").document(task_data["assigned_to_id"])
            if not assigned_to_ref.get().exists:
                raise HTTPException(status_code=404, detail=f"Usuario asignado con id {task_data['assigned_to_id']} no encontrado")
            updated_fields["assigned_to"] = assigned_to_ref

        if "created_by_id" in task_data:
            created_by_ref = db.collection("users").document(task_data["created_by_id"])
            if not created_by_ref.get().exists:
                raise HTTPException(status_code=404, detail=f"Usuario creador con id {task_data['created_by_id']} no encontrado")
            updated_fields["created_by"] = created_by_ref

        if "department_id" in task_data:
            department_ref = db.collection("departments").document(task_data["department_id"])
            if not department_ref.get().exists:
                raise HTTPException(status_code=404, detail=f"Departamento con id {task_data['department_id']} no encontrado")
            updated_fields["department"] = department_ref

        if "organization_id" in task_data:
            organization_ref = db.collection("organizations").document(task_data["organization_id"])
            if not organization_ref.get().exists:
                raise HTTPException(status_code=404, detail=f"Organización con id {task_data['organization_id']} no encontrada")
            updated_fields["organization"] = organization_ref

        for field in ["expected_outcome", "title"]:
            if field in task_data:
                updated_fields[field] = task_data[field]

        # Handle the new nested status structure
        if "status" in task_data:
            if isinstance(task_data["status"], dict) and "status" in task_data["status"]:
                updated_fields["status"] = task_data["status"]["status"]
            else:
                updated_fields["status"] = task_data["status"]

        if not updated_fields:
            raise HTTPException(status_code=400, detail="No se proporcionaron campos válidos para actualizar")

        task_ref.update(updated_fields)
        return {"message": "Tarea actualizada exitosamente", "task_id": task_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar la tarea: {e}")


@app.delete("/delete-task")
async def delete_task(task_id: str):
    try:
        task_ref = db.collection("tasks").document(task_id)
        if not task_ref.get().exists:
            raise HTTPException(status_code=404, detail=f"Tarea con id {task_id} no encontrada")

        task_ref.delete()
        return {"message": "Tarea eliminada exitosamente", "task_id": task_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar la tarea: {e}")

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

@app.get("/get-tasks-by-organization")
async def get_tasks_by_organization(organization_id: str):
    collection_ref = db.collection("tasks").where("organization", "==", db.document(f"organizations/{organization_id}"))
    docs = collection_ref.stream()

    tasks = []
    for doc in docs:
        raw_data = doc.to_dict()
        resolved_data = {}
        for key, value in raw_data.items():
            if isinstance(value, firestore.DocumentReference):
                resolved_data[key] = await resolve_document_reference(value)
            else:
                resolved_data[key] = value

        tasks.append({"id": doc.id, **resolved_data})

    if not tasks:
        return {"tasks": []}

    return {"tasks": tasks}
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
