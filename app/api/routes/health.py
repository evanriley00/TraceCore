from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request):
    runtime_snapshot = request.app.state.runtime_control.snapshot()
    return {
        "status": "ok",
        "cache_backend": request.app.state.cache.backend_name,
        "environment": request.app.state.settings.environment,
        "runtime_state": runtime_snapshot["state"],
        "active_requests": runtime_snapshot["active_requests"],
    }
