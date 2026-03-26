"""Mood Machine Web — FastAPI Server Entry Point."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from backend.api import Api
from backend.auth import authenticate, validate_session, destroy_session


# ── Request Models ────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

class ScanRequest(BaseModel):
    limit: int = 0

class GenerateRequest(BaseModel):
    prompt: str

class SavePlaylistRequest(BaseModel):
    name: str
    description: str
    song_ids: list[int]
    filter_json: str

class ExportPlexRequest(BaseModel):
    name: str
    song_ids: list[int]

class ConfigRequest(BaseModel):
    music_source_path: str = ""
    plex_url: str = ""
    plex_token: str = ""
    plex_library_name: str = "Music"
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "mistral"
    db_path: str = ""
    analysis_batch_size: int = 50


# ── App Setup ─────────────────────────────────────────────────────

api_instance: Api | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global api_instance
    api_instance = Api()
    yield

app = FastAPI(title="Mood Machine", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


# ── Auth Middleware ───────────────────────────────────────────────

# Paths that don't require authentication
PUBLIC_PATHS = {"/api/auth/login", "/api/auth/check"}

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path

    # Static files and public API endpoints don't need auth
    if not path.startswith("/api/") or path in PUBLIC_PATHS:
        return await call_next(request)

    # Check session cookie
    session_token = request.cookies.get("session")
    username = validate_session(session_token)
    if not username:
        return JSONResponse(status_code=401, content={"error": "Nicht angemeldet"})

    request.state.username = username
    return await call_next(request)


# ── Auth Routes ──────────────────────────────────────────────────

@app.post("/api/auth/login")
def login(req: LoginRequest):
    token = authenticate(req.username, req.password, api_instance.config)
    if not token:
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "Benutzername oder Passwort falsch"},
        )
    response = JSONResponse(content={"success": True, "username": req.username})
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,  # 7 days
    )
    return response

@app.post("/api/auth/logout")
def logout(session: str | None = Cookie(default=None)):
    destroy_session(session)
    response = JSONResponse(content={"success": True})
    response.delete_cookie("session")
    return response

@app.get("/api/auth/check")
def auth_check(session: str | None = Cookie(default=None)):
    username = validate_session(session)
    if username:
        return {"authenticated": True, "username": username}
    return {"authenticated": False}


# ── API Routes ────────────────────────────────────────────────────

@app.post("/api/scan/start")
def scan_start(req: ScanRequest):
    return api_instance.start_scan(req.limit)

@app.get("/api/scan/progress")
def scan_progress():
    return api_instance.get_scan_progress()

@app.get("/api/library/stats")
def library_stats():
    return api_instance.get_library_stats()

@app.post("/api/playlist/generate")
def playlist_generate(req: GenerateRequest):
    return api_instance.start_generate(req.prompt)

@app.get("/api/playlist/generate/status")
def playlist_generate_status():
    return api_instance.get_generate_status()

@app.post("/api/playlist/save")
def playlist_save(req: SavePlaylistRequest):
    return api_instance.save_playlist(req.name, req.description, req.song_ids, req.filter_json)

@app.get("/api/playlists")
def playlists_list():
    return api_instance.get_playlists()

@app.get("/api/playlist/{playlist_id}")
def playlist_load(playlist_id: int):
    return api_instance.load_playlist(playlist_id)

@app.delete("/api/playlist/{playlist_id}")
def playlist_delete(playlist_id: int):
    return api_instance.delete_playlist(playlist_id)

@app.post("/api/export/plex")
def export_plex(req: ExportPlexRequest):
    return api_instance.export_plex(req.name, req.song_ids)

@app.get("/api/config")
def config_get():
    return api_instance.get_config()

@app.put("/api/config")
def config_save(req: ConfigRequest):
    return api_instance.save_config(req.model_dump())


# ── Static Frontend ───────────────────────────────────────────────

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(_BASE_DIR, "frontend", "dist")

if os.path.isdir(FRONTEND_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        """Serve the React SPA — all non-API routes return index.html."""
        file_path = os.path.join(FRONTEND_DIR, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
