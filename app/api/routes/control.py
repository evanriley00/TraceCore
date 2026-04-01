from __future__ import annotations

from secrets import compare_digest

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.config import Settings
from app.core.deps import get_settings
from app.services.runtime_control import RuntimeControlManager

router = APIRouter(prefix="/control", tags=["control"])
bearer_scheme = HTTPBearer(auto_error=False)


class ControlActionRequest(BaseModel):
    action: str | None = None
    solutionId: str | None = None
    solutionName: str | None = None
    requestedAt: str | None = None


def get_runtime_control(request: Request) -> RuntimeControlManager:
    return request.app.state.runtime_control


def require_control_access(
    settings: Settings = Depends(get_settings),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> None:
    if not settings.control_api_token:
        return

    if credentials is None or not compare_digest(
        credentials.credentials,
        settings.control_api_token,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid control token is required.",
        )


def build_response(
    snapshot: dict[str, str | int | None],
    settings: Settings,
    message: str,
) -> dict[str, str | int | bool | None]:
    return {
        **snapshot,
        "message": message,
        "auth_required": bool(settings.control_api_token),
    }


@router.get("/status")
def status_snapshot(
    control: RuntimeControlManager = Depends(get_runtime_control),
    settings: Settings = Depends(get_settings),
    _authorized: None = Depends(require_control_access),
):
    snapshot = control.snapshot()
    return build_response(
        snapshot,
        settings,
        str(snapshot["detail"]),
    )


@router.post("/pause")
def pause_runtime(
    _payload: ControlActionRequest,
    control: RuntimeControlManager = Depends(get_runtime_control),
    settings: Settings = Depends(get_settings),
    _authorized: None = Depends(require_control_access),
):
    snapshot = control.pause()
    return build_response(
        snapshot,
        settings,
        "TraceCore intake paused successfully.",
    )


@router.post("/resume")
def resume_runtime(
    _payload: ControlActionRequest,
    control: RuntimeControlManager = Depends(get_runtime_control),
    settings: Settings = Depends(get_settings),
    _authorized: None = Depends(require_control_access),
):
    snapshot = control.resume()
    return build_response(
        snapshot,
        settings,
        "TraceCore intake resumed successfully.",
    )


@router.post("/stop")
def stop_runtime(
    _payload: ControlActionRequest,
    control: RuntimeControlManager = Depends(get_runtime_control),
    settings: Settings = Depends(get_settings),
    _authorized: None = Depends(require_control_access),
):
    snapshot = control.stop()
    return build_response(
        snapshot,
        settings,
        "TraceCore entered maintenance mode successfully.",
    )
