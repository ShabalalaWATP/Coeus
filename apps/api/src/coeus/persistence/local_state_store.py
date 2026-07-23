"""In-process and file-backed state-store implementations."""

import json
from copy import deepcopy
from pathlib import Path
from threading import RLock
from typing import Any


class MemoryStateStore:
    def __init__(self) -> None:
        self._state: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    def load(self, namespace: str) -> dict[str, Any] | None:
        with self._lock:
            payload = self._state.get(namespace)
            return deepcopy(payload) if payload is not None else None

    def save(self, namespace: str, payload: dict[str, Any]) -> None:
        with self._lock:
            self._state[namespace] = deepcopy(payload)

    def authority_guard(self) -> RLock:
        return self._lock


class FileStateStore:
    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._lock = RLock()

    def load(self, namespace: str) -> dict[str, Any] | None:
        with self._lock:
            state = self._read()
            payload = state.get(namespace)
            return payload if isinstance(payload, dict) else None

    def save(self, namespace: str, payload: dict[str, Any]) -> None:
        with self._lock:
            state = self._read()
            state[namespace] = payload
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self._path.with_suffix(f"{self._path.suffix}.tmp")
            temp_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
            temp_path.replace(self._path)

    def authority_guard(self) -> RLock:
        return self._lock

    def _read(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"State file {self._path} is not valid JSON.") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"State file {self._path} must contain a JSON object.")
        return payload
