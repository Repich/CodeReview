from __future__ import annotations

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path

from backend.app.api.router import api_router
from backend.app.core.config import get_settings
from backend.app.middleware.security import SecurityMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.project_name, debug=settings.debug)
    app.add_middleware(SecurityMiddleware)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
STATIC_ROOT = Path(__file__).resolve().parent / "static"
INDEX_FILE = STATIC_ROOT / "index.html"
DOCS_ROOT = Path(__file__).resolve().parents[2] / "docs"
TEACHER_GUIDE_FILE = DOCS_ROOT / "teacher_guide.md"


def _is_within_static(target: Path) -> bool:
    try:
        target.relative_to(STATIC_ROOT)
        return True
    except ValueError:
        return False


@app.get("/", include_in_schema=False)
async def serve_root() -> FileResponse:
    return FileResponse(INDEX_FILE)


@app.head("/", include_in_schema=False)
async def serve_index_head() -> Response:
    return Response(status_code=200)


@app.get("/help/teacher", include_in_schema=False)
async def serve_teacher_guide() -> Response:
    if TEACHER_GUIDE_FILE.is_file():
        return FileResponse(TEACHER_GUIDE_FILE)
    return Response(status_code=404)


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_static(full_path: str) -> FileResponse:
    target = (STATIC_ROOT / full_path).resolve()
    if target.is_file() and _is_within_static(target):
        return FileResponse(target)
    return FileResponse(INDEX_FILE)


@app.head("/{full_path:path}", include_in_schema=False)
async def serve_static_head(full_path: str) -> Response:
    target = (STATIC_ROOT / full_path).resolve()
    if target.is_file() and _is_within_static(target):
        return Response(status_code=200)
    return Response(status_code=200)


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
