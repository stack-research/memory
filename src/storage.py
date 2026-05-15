from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .aws_session import make_session
from .config import AwsConfig
from .epistemic_triangle import validate_event_v7
from .types import EVENT_SCHEMA_VERSION, MemoryEvent


class LineageStorage:
    def __init__(self, cfg: AwsConfig) -> None:
        self.cfg = cfg
        session = make_session(cfg)
        self.client = session.client("s3tables")
        self.s3 = session.client("s3")

    def ensure_namespace(self) -> None:
        try:
            self.client.get_namespace(
                tableBucketARN=self._table_bucket_arn(), namespace=self.cfg.table_namespace
            )
        except self.client.exceptions.NotFoundException:
            self.client.create_namespace(
                tableBucketARN=self._table_bucket_arn(), namespace=self.cfg.table_namespace
            )

    def ensure_table(self) -> None:
        try:
            self.client.get_table(
                tableBucketARN=self._table_bucket_arn(),
                namespace=self.cfg.table_namespace,
                name=self.cfg.table_name,
            )
        except self.client.exceptions.NotFoundException:
            self.client.create_table(
                tableBucketARN=self._table_bucket_arn(),
                namespace=self.cfg.table_namespace,
                name=self.cfg.table_name,
                format="ICEBERG",
                # v7 (EPISTEMIC_TRIANGLE §9.2): column order must
                # match the CDK stack's `LineageTable` schema. INSERT
                # statements in `athena_ingestion.py` project columns
                # positionally; drift between CDK and this fallback
                # would silently break ingestion. Hook in im_u
                # asserts CDK ↔ ensure_table column parity.
                metadata={
                    "iceberg": {
                        "schema": {
                            "fields": [
                                {"name": "event_id", "type": "string", "required": True},
                                {"name": "event_type", "type": "string", "required": True},
                                {"name": "agent_id", "type": "string", "required": True},
                                {"name": "stream_id", "type": "string", "required": True},
                                {"name": "memory_id", "type": "string", "required": True},
                                {"name": "payload", "type": "string", "required": False},
                                {"name": "actor_class", "type": "string", "required": True},
                                {"name": "source_class", "type": "string", "required": True},
                                {"name": "schema_version", "type": "string", "required": True},
                                {"name": "parent_event_id", "type": "string", "required": False},
                                # physical_moment JSON + Tier 1a hot
                                # columns per TAI_TIMEKEEPING §6.
                                {"name": "physical_moment", "type": "string", "required": True},
                                {"name": "pm_tai_iso", "type": "string", "required": True},
                                {"name": "pm_solar_age_myr", "type": "double", "required": True},
                                {"name": "pm_ecliptic_lon_deg", "type": "double", "required": True},
                                {"name": "pm_sequence_in_stream", "type": "long", "required": True},
                                {"name": "pm_hlc_timestamp", "type": "string", "required": True},
                                {"name": "pm_hlc_signature_eligible", "type": "boolean", "required": True},
                                {"name": "pm_time_context_id", "type": "string", "required": True},
                                # v7 envelope hot columns per
                                # EPISTEMIC_TRIANGLE §9.2.
                                {"name": "record_kind", "type": "string", "required": True},
                                {"name": "assertion_kind", "type": "string", "required": False},
                                {"name": "subject_event_id", "type": "string", "required": False},
                                {"name": "subject_record_kind", "type": "string", "required": False},
                                {"name": "subject_assertion_kind", "type": "string", "required": False},
                            ]
                        },
                        "properties": {"format-version": "2"},
                    }
                },
            )

    def append_event(self, event: MemoryEvent) -> dict[str, Any]:
        self._validate_event(event)

        # v7 ingress JSON shape (EPISTEMIC_TRIANGLE spec §9.3): no
        # legacy `event_time`. Canonical anchor is
        # physical_moment.tai_iso. Envelope carries record_kind +
        # assertion_kind + subject classification.
        tai_iso = str(event.physical_moment["tai_iso"])
        record = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "agent_id": event.agent_id,
            "stream_id": event.stream_id,
            "memory_id": event.memory_id,
            "schema_version": event.schema_version,
            "parent_event_id": event.parent_event_id,
            "actor_class": event.actor_class,
            "source_class": event.source_class,
            "payload": event.payload,
            "physical_moment": event.physical_moment,
            "record_kind": event.record_kind,
            "assertion_kind": event.assertion_kind,
            "subject_event_id": event.subject_event_id,
            "subject_record_kind": event.subject_record_kind,
            "subject_assertion_kind": event.subject_assertion_kind,
        }

        # NOTE: boto3 s3tables is control-plane only today; row writes need an Iceberg writer commit path.
        # For v0 labs, we write append-only ingress artifacts to S3 (AWS-native) and keep schema/event shape stable.
        if not self.cfg.lineage_ingress_bucket_name:
            raise ValueError(
                "AWS_S3_LINEAGE_INGRESS_BUCKET_NAME must be set for lineage event writes"
            )

        # S3 key path uses pm_tai_iso (canonical anchor) since v7
        # drops event_time. Partition by date derived from tai_iso.
        key = (
            f"{self.cfg.lineage_ingress_prefix.rstrip('/')}/"
            f"agent_id={event.agent_id}/"
            f"stream_id={event.stream_id}/"
            f"event_date={tai_iso[:10]}/"
            f"{tai_iso}_{event.event_id}.json"
        )
        self.s3.put_object(
            Bucket=self.cfg.lineage_ingress_bucket_name,
            Key=key,
            Body=json.dumps(record).encode("utf-8"),
            ContentType="application/json",
        )
        return record

    @staticmethod
    def _validate_event(event: MemoryEvent) -> None:
        required = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "agent_id": event.agent_id,
            "stream_id": event.stream_id,
            "memory_id": event.memory_id,
            "schema_version": event.schema_version,
            "actor_class": event.actor_class,
            "source_class": event.source_class,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"Missing required event fields: {', '.join(missing)}")

        if event.schema_version != EVENT_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported schema_version '{event.schema_version}', expected '{EVENT_SCHEMA_VERSION}'"
            )

        if not isinstance(event.payload, dict):
            raise ValueError("Event payload must be a JSON object/dict")

        # v6 physical_moment validation — Tier 1a non-nullable per
        # TAI_TIMEKEEPING spec §5.1 (carried into v7 unchanged).
        if not isinstance(event.physical_moment, dict):
            raise ValueError("Event physical_moment must be a JSON object/dict")
        tier1a_required = (
            "tai_iso",
            "solar_age_myr",
            "ecliptic_lon_deg",
            "sequence_in_stream",
            "hlc_timestamp",
            "time_context_id",
        )
        for field_name in tier1a_required:
            if event.physical_moment.get(field_name) is None:
                raise ValueError(
                    f"physical_moment.{field_name} is required (Tier 1a non-nullable)"
                )
        try:
            datetime.fromisoformat(event.physical_moment["tai_iso"])
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"Invalid physical_moment.tai_iso ISO format: {event.physical_moment.get('tai_iso')}"
            ) from exc

        # v7 envelope validation — EPISTEMIC_TRIANGLE spec §3.6.
        # Build the dict view validate_event_v7 expects (it operates
        # on a Mapping, not the dataclass).
        event_view = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "agent_id": event.agent_id,
            "stream_id": event.stream_id,
            "memory_id": event.memory_id,
            "schema_version": event.schema_version,
            "actor_class": event.actor_class,
            "source_class": event.source_class,
            "payload": event.payload,
            "physical_moment": event.physical_moment,
            "record_kind": event.record_kind,
            "assertion_kind": event.assertion_kind,
            "subject_event_id": event.subject_event_id,
            "subject_record_kind": event.subject_record_kind,
            "subject_assertion_kind": event.subject_assertion_kind,
            # event_time deliberately absent — v7 events MUST NOT
            # carry it. validate_event_v7 quarantines if present.
        }
        v7_failure = validate_event_v7(event_view)
        if v7_failure is not None:
            raise ValueError(
                f"v7 envelope validation failed [{v7_failure.reason}]: {v7_failure.detail}"
            )

    def _table_bucket_arn(self) -> str:
        region = self.cfg.region
        account_id = make_session(self.cfg).client("sts").get_caller_identity()["Account"]
        return f"arn:aws:s3tables:{region}:{account_id}:bucket/{self.cfg.table_bucket_name}"
