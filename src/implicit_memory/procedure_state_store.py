from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Protocol

from src.implicit_memory.procedure_lifecycle import ProcedureState

if TYPE_CHECKING:
    from src.config import AwsConfig


@dataclass
class PersistedProcedureState:
    procedure_id: str
    strength: float
    trust: float
    high_urgency_streak: int
    updated_at: str
    last_event_id: str | None = None


class ProcedureStateStore(Protocol):
    def load(self, *, procedure_id: str) -> ProcedureState | None: ...

    def save(self, *, state: ProcedureState, last_event_id: str | None = None) -> PersistedProcedureState: ...


class InMemoryProcedureStateStore:
    def __init__(self) -> None:
        self._rows: dict[str, PersistedProcedureState] = {}

    def load(self, *, procedure_id: str) -> ProcedureState | None:
        row = self._rows.get(procedure_id)
        if not row:
            return None
        return ProcedureState(
            procedure_id=row.procedure_id,
            strength=row.strength,
            trust=row.trust,
            high_urgency_streak=row.high_urgency_streak,
        )

    def save(self, *, state: ProcedureState, last_event_id: str | None = None) -> PersistedProcedureState:
        row = PersistedProcedureState(
            procedure_id=state.procedure_id,
            strength=state.strength,
            trust=state.trust,
            high_urgency_streak=state.high_urgency_streak,
            updated_at=datetime.now(timezone.utc).isoformat(),
            last_event_id=last_event_id,
        )
        self._rows[state.procedure_id] = row
        return row


class S3ProcedureStateStore:
    def __init__(self, cfg: "AwsConfig") -> None:
        from src.aws_session import make_session

        self.cfg = cfg
        session = make_session(cfg)
        self.s3 = session.client("s3")
        self.bucket = cfg.procedure_state_bucket_name or cfg.lineage_ingress_bucket_name
        self.prefix = cfg.procedure_state_prefix.rstrip("/")
        if not self.bucket:
            raise ValueError("No procedure state bucket configured")

    def _key(self, procedure_id: str) -> str:
        return f"{self.prefix}/procedure_id={procedure_id}.json"

    def load(self, *, procedure_id: str) -> ProcedureState | None:
        try:
            obj = self.s3.get_object(Bucket=self.bucket, Key=self._key(procedure_id))
        except self.s3.exceptions.NoSuchKey:
            return None
        except Exception as exc:
            msg = str(exc)
            if "NoSuchKey" in msg or "404" in msg:
                return None
            raise

        body = obj["Body"].read().decode("utf-8")
        row = json.loads(body)
        return ProcedureState(
            procedure_id=row["procedure_id"],
            strength=float(row.get("strength", 1.0)),
            trust=float(row.get("trust", 1.0)),
            high_urgency_streak=int(row.get("high_urgency_streak", 0)),
        )

    def save(self, *, state: ProcedureState, last_event_id: str | None = None) -> PersistedProcedureState:
        row = PersistedProcedureState(
            procedure_id=state.procedure_id,
            strength=state.strength,
            trust=state.trust,
            high_urgency_streak=state.high_urgency_streak,
            updated_at=datetime.now(timezone.utc).isoformat(),
            last_event_id=last_event_id,
        )
        self.s3.put_object(
            Bucket=self.bucket,
            Key=self._key(state.procedure_id),
            Body=json.dumps(asdict(row)).encode("utf-8"),
            ContentType="application/json",
        )
        return row
