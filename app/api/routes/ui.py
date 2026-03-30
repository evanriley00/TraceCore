from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, RedirectResponse

ROOT_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = ROOT_DIR / "static"

router = APIRouter(tags=["ui"])


@router.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/ui", status_code=307)


@router.get("/ui", include_in_schema=False)
def ui():
    return FileResponse(STATIC_DIR / "index.html")

