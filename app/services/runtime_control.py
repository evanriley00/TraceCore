from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Literal

RuntimeControlState = Literal["running", "paused", "stopped"]

OBSERVABILITY_PATH_PREFIXES = (
    "/control",
    "/health",
    "/ui",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/static",
)
MAINTENANCE_OPERATOR_PATHS = {
    ("POST", "/auth/login"),
    ("GET", "/auth/me"),
}
INTAKE_PATHS = {
    ("POST", "/v1/query"),
    ("POST", "/v1/documents/ingest"),
    ("POST", "/v1/feedback"),
}


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class RuntimeControlManager:
    def __init__(self, state_path: str):
        resolved_path = Path(state_path)
        self._state_path = (
            resolved_path
            if resolved_path.is_absolute()
            else Path.cwd() / resolved_path
        )
        self._lock = RLock()
        self._active_requests = 0
        self._state = self._load_state()

    def _default_state(self) -> dict[str, str | None]:
        return {
            "state": "running",
            "last_action": "resume",
            "last_transition_at": utc_now_iso(),
            "detail": "TraceCore is accepting new intake.",
        }

    def _load_state(self) -> dict[str, str | None]:
        if not self._state_path.exists():
            state = self._default_state()
            self._persist_state(state)
            return state

        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        except Exception:
            state = self._default_state()
            self._persist_state(state)
            return state

        state = self._default_state()
        state["state"] = payload.get("state", state["state"])
        state["last_action"] = payload.get("last_action", state["last_action"])
        state["last_transition_at"] = payload.get(
            "last_transition_at",
            state["last_transition_at"],
        )
        state["detail"] = payload.get("detail", state["detail"])
        return state

    def _persist_state(self, state: dict[str, str | None]) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(
            json.dumps(state, indent=2),
            encoding="utf-8",
        )

    def snapshot(self) -> dict[str, str | int | None]:
        with self._lock:
            return {
                "state": self._state["state"],
                "status": self._state["state"],
                "last_action": self._state["last_action"],
                "last_transition_at": self._state["last_transition_at"],
                "detail": self._state["detail"],
                "active_requests": self._active_requests,
            }

    def transition(
        self,
        state: RuntimeControlState,
        action: Literal["pause", "resume", "stop"],
        detail: str,
    ) -> dict[str, str | int | None]:
        with self._lock:
            self._state = {
                "state": state,
                "last_action": action,
                "last_transition_at": utc_now_iso(),
                "detail": detail,
            }
            self._persist_state(self._state)
            return self.snapshot()

    def pause(self) -> dict[str, str | int | None]:
        return self.transition(
            "paused",
            "pause",
            "TraceCore intake is paused. New query, ingest, and feedback requests will return 503 until resumed.",
        )

    def resume(self) -> dict[str, str | int | None]:
        return self.transition(
            "running",
            "resume",
            "TraceCore is accepting new intake.",
        )

    def stop(self) -> dict[str, str | int | None]:
        return self.transition(
            "stopped",
            "stop",
            "TraceCore is in maintenance mode. Business routes are disabled while operator login, health, and control access remain available.",
        )

    def begin_request(self) -> None:
        with self._lock:
            self._active_requests += 1

    def end_request(self) -> None:
        with self._lock:
            self._active_requests = max(0, self._active_requests - 1)


def is_observability_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in OBSERVABILITY_PATH_PREFIXES)


def is_maintenance_operator_path(method: str, path: str) -> bool:
    return (method.upper(), path) in MAINTENANCE_OPERATOR_PATHS


def blocks_request(state: RuntimeControlState, method: str, path: str) -> bool:
    if is_observability_path(path):
        return False

    if state == "paused":
        return (method.upper(), path) in INTAKE_PATHS

    if state == "stopped":
        return not is_maintenance_operator_path(method, path)

    return False


def should_track_request(path: str) -> bool:
    return not is_observability_path(path) and not path.startswith("/auth")
