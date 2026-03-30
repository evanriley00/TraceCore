from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request):
    return {
        "status": "ok",
        "cache_backend": request.app.state.cache.backend_name,
        "environment": request.app.state.settings.environment,
    }

