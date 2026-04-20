from fastapi import FastAPI, APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import uuid
import aiofiles
from pathlib import Path
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone

from voices import VOICES, LANGUAGES, get_voice
from pipeline import run_pipeline, ffprobe_duration, STORAGE_ROOT

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB per file

app = FastAPI(title="Viral Video Editor")
api = APIRouter(prefix="/api")


def _now():
    return datetime.now(timezone.utc).isoformat()


# --------------------------- models ---------------------------
class CreateProjectRequest(BaseModel):
    name: str
    voice: str
    language: str = "en"
    user_prompt: str = ""
    audience: str = "35-50 year old adults"
    target_duration_s: float = 85.0


# --------------------------- meta ---------------------------
@api.get("/")
async def root():
    return {"service": "viral-video-editor", "status": "ok"}


@api.get("/voices")
async def list_voices():
    return {"voices": VOICES, "languages": LANGUAGES}


# --------------------------- projects CRUD ---------------------------
@api.post("/projects")
async def create_project(req: CreateProjectRequest):
    if not get_voice(req.voice):
        raise HTTPException(400, "Unknown voice id")
    pid = str(uuid.uuid4())
    doc = {
        "id": pid,
        "name": req.name or "Untitled project",
        "voice": req.voice,
        "language": req.language,
        "user_prompt": req.user_prompt,
        "audience": req.audience,
        "target_duration_s": req.target_duration_s,
        "status": "draft",
        "progress": 0,
        "source_files": [],
        "logs": [],
        "plan": None,
        "analyses": None,
        "output": None,
        "error": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.projects.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.get("/projects")
async def list_projects():
    items = await db.projects.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"projects": items}


@api.get("/projects/{pid}")
async def get_project(pid: str):
    p = await db.projects.find_one({"id": pid}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Project not found")
    return p


@api.delete("/projects/{pid}")
async def delete_project(pid: str):
    p = await db.projects.find_one({"id": pid}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Project not found")
    # Cleanup storage
    workdir = STORAGE_ROOT / pid
    if workdir.exists():
        import shutil
        shutil.rmtree(workdir, ignore_errors=True)
    await db.projects.delete_one({"id": pid})
    return {"deleted": True}


# --------------------------- upload ---------------------------
@api.post("/projects/{pid}/upload")
async def upload_files(pid: str, files: List[UploadFile] = File(...)):
    p = await db.projects.find_one({"id": pid}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Project not found")
    if p["status"] not in ("draft",):
        raise HTTPException(400, "Cannot add files after processing has started")

    workdir = STORAGE_ROOT / pid / "src"
    workdir.mkdir(parents=True, exist_ok=True)

    saved = list(p.get("source_files", []))
    for uf in files:
        # Basic validation
        ext = Path(uf.filename or "file.mp4").suffix.lower()
        if ext not in (".mp4", ".mov", ".m4v"):
            raise HTTPException(400, f"Unsupported file type: {ext}")
        safe_name = f"{uuid.uuid4().hex}{ext}"
        dest = workdir / safe_name
        size = 0
        async with aiofiles.open(dest, "wb") as f:
            while chunk := await uf.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    await f.close()
                    dest.unlink(missing_ok=True)
                    raise HTTPException(413, f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)}MB")
                await f.write(chunk)
        dur = await ffprobe_duration(str(dest))
        saved.append({
            "filename": uf.filename,
            "path": str(dest),
            "size_bytes": size,
            "size_mb": round(size / (1024 * 1024), 2),
            "duration": round(dur, 2),
        })
    await db.projects.update_one(
        {"id": pid},
        {"$set": {"source_files": saved, "updated_at": _now()}},
    )
    return {"source_files": saved}


# --------------------------- process ---------------------------
@api.post("/projects/{pid}/process")
async def process_project(pid: str, background: BackgroundTasks):
    p = await db.projects.find_one({"id": pid}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Project not found")
    if not p.get("source_files"):
        raise HTTPException(400, "Upload at least one video first")
    if p["status"] in ("analyzing", "planning", "rendering"):
        raise HTTPException(409, "Already processing")

    await db.projects.update_one(
        {"id": pid},
        {"$set": {"status": "queued", "progress": 1, "error": None, "logs": [], "updated_at": _now()}},
    )
    background.add_task(run_pipeline, db, pid)
    return {"queued": True}


# --------------------------- download ---------------------------
@api.get("/projects/{pid}/download")
async def download_final(pid: str):
    p = await db.projects.find_one({"id": pid}, {"_id": 0})
    if not p or not p.get("output"):
        raise HTTPException(404, "Final video not ready")
    out = p["output"]
    path = out["path"]
    if not Path(path).exists():
        raise HTTPException(404, "File missing on disk")
    return FileResponse(
        path=path,
        media_type="video/mp4",
        filename=out.get("filename", "viral_final.mp4"),
        headers={"Accept-Ranges": "bytes"},
    )


@api.get("/projects/{pid}/stream")
async def stream_final(pid: str):
    return await download_final(pid)


# --------------------------- wiring ---------------------------
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def on_start():
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    await db.projects.create_index("id", unique=True)


@app.on_event("shutdown")
async def on_stop():
    client.close()
