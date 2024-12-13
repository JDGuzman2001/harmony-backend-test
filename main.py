import os
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from google.cloud import firestore
from dotenv import load_dotenv
import asyncio
from typing import List, Dict, Any

load_dotenv()

credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if not credentials_path:
    raise Exception("GOOGLE_APPLICATION_CREDENTIALS is not defined in the environment variables.")

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise Exception("OPENAI_API_KEY is not defined in the environment variables.")

client = OpenAI(
    api_key= api_key
)


db = firestore.Client()

app = FastAPI()

origins = [
    '*'
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
        return {"id": ref.id, "path": str(ref.path), "error": "Circular reference detected"}

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
            return {"error": "Document not found", "path": str(ref.path)}
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


# -------------------------------------------------------------- CHATBOT --------------------------------------------------------------
@app.post("/get-answer-to-chat")
async def get_answer_to_chat(user_question: dict = Body(...)):
    message = user_question.get("message")
    user_id = user_question.get("user_id")
    if not message or not user_id:
        raise HTTPException(status_code=400, detail="Both 'message' and 'user_id' are required.")

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a useful assistant. Based on the user's input, "
                    "generate an array of 5 JSON objects. Each object should represent "
                    "a different workflow or approach to achieve the user's request. "
                    "Each object should include: 'name' (a brief name of the workflow), "
                    "'description' (a short explanation), and 'steps' (an array of 3-5 steps "
                    "to execute the workflow). Structure the response as valid JSON and nothing else. "
                )
            },
            {"role": "user", "content": message}
        ],
        temperature=0,
    )

    answer_json = response.choices[0].message.content

    user_ref = db.collection("users").document(user_id)

    db.collection("ia_answers").add({
        "ia_answer": answer_json,
        "user": user_ref,
        "user_message": message
    })
    return {"message": answer_json}

@app.get("/get-user-messages")
async def get_user_messages(user_id: str):
    user_ref = db.collection("users").document(user_id)
    collection_ref = db.collection("ia_answers").where("user", "==", user_ref)
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

        print(data)

    if not data:
        raise HTTPException(status_code=404, detail="No data found for the specified user")

    return {"user_messages": data[0]}

# -------------------------------------------------------------- ORGANIZATION CRUD --------------------------------------------------------------
@app.get("/get-organization-info")
async def get_organization_info(organization_id: str):
    organization_ref = db.collection("organizations").document(organization_id)

    org_doc = organization_ref.get()

    if not org_doc.exists:
        raise HTTPException(status_code=404, detail="Organization not found")

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
                            detail="No departments or users were found for the specified organization")

    return {
        'organization': response_data
    }


# -------------------------------------------------------------- USERS CRUD --------------------------------------------------------------
@app.post("/create-user")
async def create_user(user_data: dict = Body(...)):
    try:
        role_id = user_data.get("role_id")
        if not role_id:
            raise HTTPException(status_code=400, detail="role_id is required")

        role_ref = db.collection("roles").document(role_id)
        role_doc = role_ref.get()

        if not role_doc.exists:
            raise HTTPException(status_code=404, detail=f"Role with id {role_id} no found")

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

        return {"message": "User created successfully", "user_id": doc_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating user: {e}")

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
        raise HTTPException(status_code=404, detail="No data found for the specified user")

    return {"user_info": data[0]}

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
        raise HTTPException(status_code=404, detail="No data found for the specified user")

    return {"roles": data}


# -------------------------------------------------------------- TASKS CRUD --------------------------------------------------------------
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
            raise HTTPException(status_code=400, detail="All fields are required")

        assigned_to_ref = db.collection("users").document(assigned_to_id)
        created_by_ref = db.collection("users").document(created_by_id)
        department_ref = db.collection("departments").document(department_id)
        organization_ref = db.collection("organizations").document(organization_id)

        if not assigned_to_ref.get().exists:
            raise HTTPException(status_code=404, detail=f"User assigned with id {assigned_to_id} not found")

        if not created_by_ref.get().exists:
            raise HTTPException(status_code=404, detail=f"User assigned with id {created_by_id} not found")

        if not department_ref.get().exists:
            raise HTTPException(status_code=404, detail=f"Department with id {department_id} not found")

        if not organization_ref.get().exists:
            raise HTTPException(status_code=404, detail=f"Organization with id {organization_id} not found")

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

        return {"message": "Task created successfully", "task_id": task_ref[1].id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating task: {e}")

@app.put("/update-task")
async def update_task(task_id: str, task_data: dict = Body(...)):
    try:
        task_ref = db.collection("tasks").document(task_id)
        if not task_ref.get().exists:
            raise HTTPException(status_code=404, detail=f"Task with id {task_id} not found")

        updated_fields = {}
        if "assigned_to_id" in task_data:
            assigned_to_ref = db.collection("users").document(task_data["assigned_to_id"])
            if not assigned_to_ref.get().exists:
                raise HTTPException(status_code=404, detail=f"User assigned with id {task_data['assigned_to_id']} not found")
            updated_fields["assigned_to"] = assigned_to_ref

        if "created_by_id" in task_data:
            created_by_ref = db.collection("users").document(task_data["created_by_id"])
            if not created_by_ref.get().exists:
                raise HTTPException(status_code=404, detail=f"User assigned with id {task_data['created_by_id']} not found")
            updated_fields["created_by"] = created_by_ref

        if "department_id" in task_data:
            department_ref = db.collection("departments").document(task_data["department_id"])
            if not department_ref.get().exists:
                raise HTTPException(status_code=404, detail=f"Department with id {task_data['department_id']} not found")
            updated_fields["department"] = department_ref

        if "organization_id" in task_data:
            organization_ref = db.collection("organizations").document(task_data["organization_id"])
            if not organization_ref.get().exists:
                raise HTTPException(status_code=404, detail=f"Organization with id {task_data['organization_id']} not found")
            updated_fields["organization"] = organization_ref

        for field in ["expected_outcome", "title"]:
            if field in task_data:
                updated_fields[field] = task_data[field]

        if "status" in task_data:
            if isinstance(task_data["status"], dict) and "status" in task_data["status"]:
                updated_fields["status"] = task_data["status"]["status"]
            else:
                updated_fields["status"] = task_data["status"]

        if not updated_fields:
            raise HTTPException(status_code=400, detail="No valid fields were provided to update")

        task_ref.update(updated_fields)
        return {"message": "Task updated successfully", "task_id": task_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating task: {e}")


@app.delete("/delete-task")
async def delete_task(task_id: str):
    try:
        task_ref = db.collection("tasks").document(task_id)
        if not task_ref.get().exists:
            raise HTTPException(status_code=404, detail=f"Task with id {task_id} not found")

        task_ref.delete()
        return {"message": "Task deleted successfully", "task_id": task_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting task: {e}")


# -------------------------------------------------------------- WORKFLOWS CRUD --------------------------------------------------------------
@app.post("/create-workflow")
async def create_workflow(workflow_data: dict = Body(...)):
    try:
        created_by_id = workflow_data.get("created_by_id")
        title = workflow_data.get("title")
        description = workflow_data.get("description")
        organization_id = workflow_data.get("organization_id")

        if not all([created_by_id, title, organization_id]):
            raise HTTPException(status_code=400, detail="All fields are required")

        created_by_ref = db.collection("users").document(created_by_id)
        organization_ref = db.collection("organizations").document(organization_id)

        if not created_by_ref.get().exists:
            raise HTTPException(status_code=404, detail=f"Creator user with id {created_by_id} not found")

        if not organization_ref.get().exists:
            raise HTTPException(status_code=404, detail=f"Organization with id {organization_id} not found")

        workflow_data = {
            "created_by": created_by_ref,
            "organization": organization_ref,
            "title": title,
            "description": description
        }

        workflow_ref = db.collection("workflows").add(workflow_data)

        return {"message": "Workflow created successfully", "workflow_id": workflow_ref[1].id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating workflow: {e}")

@app.delete("/delete-workflow")
async def delete_workflow(workflow_id: str):
    try:
        workflow_ref = db.collection("workflows").document(workflow_id)
        if not workflow_ref.get().exists:
            raise HTTPException(status_code=404, detail=f"Workflow with id {workflow_id} not found")

        nodes_query = db.collection("nodes").where("workflow", "==", workflow_ref).stream()
        for node in nodes_query:
            db.collection("nodes").document(node.id).delete()

        edges_query = db.collection("edges").where("workflow", "==", workflow_ref).stream()
        for edge in edges_query:
            db.collection("edges").document(edge.id).delete()

        workflow_ref.delete()

        return {"message": "Workflow successfully deleted", "workflow_id": workflow_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting workflow: {e}")
@app.get("/get-workflows-by-organization")
async def get_workflows_by_organization(organization_id: str):
    collection_ref = db.collection("workflows").where("organization", "==", db.document(f"organizations/{organization_id}"))
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
        raise HTTPException(status_code=404, detail="No data found for the specified user")

    return {"workflows": data}

@app.get("/get-nodes-by-workflow")
async def get_workflows_by_workflow(workflow_id: str):
    collection_ref = db.collection("nodes").where("workflow", "==", db.document(f"workflows/{workflow_id}"))
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
        return {"nodes": []}

    return {"nodes": data}

@app.get("/get-edges-by-workflow")
async def get_edges_by_workflow(workflow_id: str):
    collection_ref = db.collection("edges").where("workflow", "==", db.document(f"workflows/{workflow_id}"))
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
        return {"edge": []}

    return {"edges": data}


@app.post("/create-node")
async def create_node(workflow_id: str, node_data: dict = Body(...)):

    if not workflow_id:
        raise HTTPException(status_code=400, detail="workflow_id is required")

    if not node_data.get("id"):
        raise HTTPException(status_code=400, detail="Node ID is required")

    try:
        workflow_ref = db.collection("workflows").document(workflow_id)

        node_id = node_data["id"]
        node_ref = db.collection("nodes").document(node_id)

        node_document = {
            "type": node_data.get("type"),
            "position": node_data.get("position", {}),
            "data": node_data.get("data", {}),
            "width": node_data.get("width"),
            "height": node_data.get("height"),
            "selected": node_data.get("selected", False),
            "positionAbsolute": node_data.get("positionAbsolute", {}),
            "dragging": node_data.get("dragging", False),
            "workflow": workflow_ref
        }

        node_ref.set(node_document, merge=True)

        return {"node": "Node created"}

    except Exception as e:
        print(f"Error al crear nodo: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating node: {str(e)}")

@app.put("/update-nodes")
async def update_nodes(nodes_data: dict = Body(...)):
    nodes = nodes_data.get("nodes", [])
    edges = nodes_data.get("edges", [])
    workflow_id = nodes_data.get("workflow_id")

    if not workflow_id:
        raise HTTPException(status_code=400, detail="workflow_id is required")

    try:
        workflow_ref = db.collection("workflows").document(workflow_id)

        existing_nodes_query = db.collection("nodes").where("workflow", "==", workflow_ref).stream()
        existing_edges_query = db.collection("edges").where("workflow", "==", workflow_ref).stream()

        existing_node_ids = set()
        incoming_node_ids = set(node.get("id") for node in nodes)

        existing_edge_ids = set()
        incoming_edge_ids = set(edge.get("id") for edge in edges)

        for node in nodes:
            node_id = node.get("id")
            if not node_id:
                continue

            node_ref = db.collection("nodes").document(node_id)
            node_data = {
                "type": node.get("type"),
                "position": node.get("position", {}),
                "data": node.get("data", {}),
                "width": node.get("width"),
                "height": node.get("height"),
                "selected": node.get("selected", False),
                "positionAbsolute": node.get("positionAbsolute", {}),
                "dragging": node.get("dragging", False),
                "workflow": workflow_ref
            }

            node_ref.set(node_data, merge=True)
            existing_node_ids.add(node_id)

        for edge in edges:
            edge_id = edge.get("id")
            if not edge_id:
                continue

            edge_ref = db.collection("edges").document(edge_id)
            edge_data = {
                "source": edge.get("source"),
                "sourceHandle": edge.get("sourceHandle"),
                "target": edge.get("target"),
                "targetHandle": edge.get("targetHandle"),
                "workflow": workflow_ref
            }

            edge_ref.set(edge_data, merge=True)
            existing_edge_ids.add(edge_id)

        for existing_node in existing_nodes_query:
            if existing_node.id not in incoming_node_ids:
                db.collection("nodes").document(existing_node.id).delete()

        for existing_edge in existing_edges_query:
            if existing_edge.id not in incoming_edge_ids:
                db.collection("edges").document(existing_edge.id).delete()

        return {"message": "Nodes and edges updated successfully."}

    except Exception as e:
        print(f"Error al actualizar nodos y aristas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating nodes and edges: {str(e)}")

# -------------------------------------------------------------- PRODUCTS CRUD --------------------------------------------------------------
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
        raise HTTPException(status_code=404, detail="No data found for the specified city")

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
        raise HTTPException(status_code=404, detail="No data found for the specified filters")

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
        raise HTTPException(status_code=404, detail="No data found for the countries")

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
        raise HTTPException(status_code=404, detail="No data found for the routes")

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
        raise HTTPException(status_code=404, detail="No data found for the specified country")

    return {"zones": list(zones.values())}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)
