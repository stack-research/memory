from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from memory_lab.audit import AuditAPI
from memory_lab.cloud_service import S3MemoryLabService
from memory_lab.config import Settings, load_dotenv
from memory_lab.service import MemoryLabService


def _json_response(status_code: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload),
    }


def _parse_body(event: dict[str, Any]) -> dict[str, Any]:
    body = event.get("body")
    if body is None:
        return {}
    if isinstance(body, str):
        return json.loads(body)
    return body


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    load_dotenv()
    settings = Settings.from_env()
    root = Path(settings.memory_root)
    root.mkdir(parents=True, exist_ok=True)

    if settings.storage_mode == "local":
        service: Any = MemoryLabService(root, settings=settings)
        audit: Any = AuditAPI(root)
    else:
        service = S3MemoryLabService(
            events_bucket=settings.aws_events_bucket_name,
            state_bucket=settings.aws_state_bucket_name,
            vector_bucket=settings.aws_vector_bucket_name,
            vector_index_name=settings.aws_vector_index_name,
            region=settings.aws_region,
        )
        audit = service

    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method")
    path = event.get("path") or event.get("rawPath", "")
    path_params = event.get("pathParameters") or {}

    try:
        if method == "POST" and path.endswith("/events"):
            body = _parse_body(event)
            inserted = service.ingest_event(
                memory_id=body["memory_id"],
                sequence=int(body["sequence"]),
                event_type=body["event_type"],
                payload=body.get("payload", {}),
                source=body["source"],
            )
            return _json_response(200, {"inserted": inserted})

        if method == "POST" and path.endswith("/retrieve"):
            body = _parse_body(event)
            ranked = service.retrieve(query=body["query"], top_k=int(body.get("top_k", 10)))
            return _json_response(200, {"results": ranked})

        if method == "GET" and path.endswith("/beliefs/current"):
            return _json_response(200, {"beliefs": audit.beliefs_current()})

        if method == "GET" and "/memory/" in path and path.endswith("/lineage"):
            memory_id = path_params.get("id")
            if not memory_id:
                parts = [p for p in path.split("/") if p]
                if len(parts) >= 2:
                    memory_id = parts[-2]
            if not memory_id:
                return _json_response(400, {"error": "missing memory id"})
            return _json_response(200, {"lineage": audit.memory_lineage(memory_id)})

        return _json_response(404, {"error": "route not found"})
    except KeyError as exc:
        return _json_response(400, {"error": f"missing required field: {exc.args[0]}"})
    except Exception as exc:  # pragma: no cover - safety response path
        return _json_response(500, {"error": str(exc)})
