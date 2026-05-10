from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _artifact_dir() -> Path:
    root = Path(os.environ.get("IMPLICIT_ARTIFACT_DIR", "artifacts/implicit"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def write_artifact(*, name: str, payload: dict[str, Any]) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = _artifact_dir() / f"{name}-{ts}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)
