import os
import uuid
import json
import time
from typing import Optional, List
from fastapi import FastAPI, Header, HTTPException, UploadFile, File, Form, Query, Depends
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, PointIdsList

# ============ 配置 ============
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
API_KEY    = os.getenv("API_KEY", "changeme")
COLLECTION = "memories"
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
VECTOR_SIZE = 384

# ============ 初始化 ============
app = FastAPI(title="Self-hosted Memory API")
model = SentenceTransformer(MODEL_NAME)
qdrant = QdrantClient(url=QDRANT_URL)

def ensure_collection():
    try:
        qdrant.get_collection(COLLECTION)
    except Exception:
        qdrant.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
        )

ensure_collection()

# ============ Auth ============
def verify_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

# ============ Schemas ============
class MemoryCreate(BaseModel):
    content: str
    tags: Optional[List[str]] = []
    source: Optional[str] = None

class MemoryUpdate(BaseModel):
    content: str
    tags: Optional[List[str]] = []
    source: Optional[str] = None

# ============ 临时存储 import 任务状态 ============
import_tasks: dict = {}

# ============ 路由 ============

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.post("/v1alpha1/mem9s")
def provision_tenant():
    """兼容 mem9 开通接口，直接返回配置好的 API Key"""
    return {"id": API_KEY}

@app.post("/v1alpha2/mem9s/memories", dependencies=[Depends(verify_key)])
def create_memory(body: MemoryCreate):
    mem_id = str(uuid.uuid4())
    vector = model.encode(body.content).tolist()
    qdrant.upsert(
        collection_name=COLLECTION,
        points=[PointStruct(
            id=mem_id,
            vector=vector,
            payload={
                "content": body.content,
                "tags": body.tags,
                "source": body.source,
                "created_at": time.time()
            }
        )]
    )
    return {"id": mem_id, "content": body.content, "tags": body.tags, "source": body.source}

@app.get("/v1alpha2/mem9s/memories", dependencies=[Depends(verify_key)])
def search_memories(
    q: Optional[str] = Query(None),
    limit: int = Query(10),
    source: Optional[str] = Query(None),
):
    if q:
        vector = model.encode(q).tolist()
        results = qdrant.search(
            collection_name=COLLECTION,
            query_vector=vector,
            limit=limit,
            with_payload=True
        )
        memories = [{"id": str(r.id), **r.payload, "score": r.score} for r in results]
    else:
        results, _ = qdrant.scroll(
            collection_name=COLLECTION,
            limit=limit,
            with_payload=True
        )
        memories = [{"id": str(r.id), **r.payload} for r in results]
    return {"memories": memories, "total": len(memories)}

@app.get("/v1alpha2/mem9s/memories/{mem_id}", dependencies=[Depends(verify_key)])
def get_memory(mem_id: str):
    results = qdrant.retrieve(
        collection_name=COLLECTION,
        ids=[mem_id],
        with_payload=True
    )
    if not results:
        raise HTTPException(status_code=404, detail="Memory not found")
    r = results[0]
    return {"id": str(r.id), **r.payload}

@app.put("/v1alpha2/mem9s/memories/{mem_id}", dependencies=[Depends(verify_key)])
def update_memory(mem_id: str, body: MemoryUpdate):
    vector = model.encode(body.content).tolist()
    qdrant.upsert(
        collection_name=COLLECTION,
        points=[PointStruct(
            id=mem_id,
            vector=vector,
            payload={
                "content": body.content,
                "tags": body.tags,
                "source": body.source,
                "updated_at": time.time()
            }
        )]
    )
    return {"id": mem_id, "content": body.content}

@app.delete("/v1alpha2/mem9s/memories/{mem_id}", dependencies=[Depends(verify_key)])
def delete_memory(mem_id: str):
    qdrant.delete(
        collection_name=COLLECTION,
        points_selector=PointIdsList(points=[mem_id])
    )
    return {"deleted": mem_id}

@app.post("/v1alpha2/mem9s/imports", dependencies=[Depends(verify_key)])
async def import_file(
    file: UploadFile = File(...),
    file_type: str = Form(...),
    session_id: Optional[str] = Form(None),
    agent_id: Optional[str] = Form(None),
):
    task_id = str(uuid.uuid4())
    import_tasks[task_id] = {"status": "processing", "created_at": time.time()}
    content = await file.read()
    try:
        data = json.loads(content)
        items = data if isinstance(data, list) else [data]
        points = []
        for item in items:
            text = item.get("content") or item.get("text") or str(item)
            if text:
                vector = model.encode(text).tolist()
                points.append(PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={
                        "content": text,
                        "tags": item.get("tags", []),
                        "source": agent_id or file_type,
                        "created_at": time.time()
                    }
                ))
        if points:
            qdrant.upsert(collection_name=COLLECTION, points=points)
        import_tasks[task_id]["status"] = "done"
        import_tasks[task_id]["imported"] = len(points)
    except Exception as e:
        import_tasks[task_id]["status"] = "failed"
        import_tasks[task_id]["error"] = str(e)
    return {"id": task_id, **import_tasks[task_id]}

@app.get("/v1alpha2/mem9s/imports", dependencies=[Depends(verify_key)])
def list_imports():
    return {"imports": [{"id": k, **v} for k, v in import_tasks.items()]}

@app.get("/v1alpha2/mem9s/imports/{task_id}", dependencies=[Depends(verify_key)])
def get_import(task_id: str):
    if task_id not in import_tasks:
        raise HTTPException(status_code=404)
    return {"id": task_id, **import_tasks[task_id]}
