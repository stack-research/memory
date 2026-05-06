from __future__ import annotations

import json
from typing import Any

from .aws_session import make_session
from .config import AwsConfig
from .types import MemoryEvent


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
                withoutMetadata="Yes",
            )

    def append_event(self, event: MemoryEvent) -> dict[str, Any]:
        record = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "agent_id": event.agent_id,
            "stream_id": event.stream_id,
            "memory_id": event.memory_id,
            "event_time": event.event_time,
            "parent_event_id": event.parent_event_id,
            "payload": event.payload,
        }

        # NOTE: boto3 s3tables is control-plane only today; row writes need an Iceberg writer commit path.
        # For v0 labs, we write append-only ingress artifacts to S3 (AWS-native) and keep schema/event shape stable.
        if not self.cfg.lineage_ingress_bucket_name:
            raise ValueError(
                "AWS_S3_LINEAGE_INGRESS_BUCKET_NAME must be set for lineage event writes"
            )

        key = (
            f"{self.cfg.lineage_ingress_prefix.rstrip('/')}/"
            f"agent_id={event.agent_id}/"
            f"stream_id={event.stream_id}/"
            f"event_date={event.event_time[:10]}/"
            f"{event.event_time}_{event.event_id}.json"
        )
        self.s3.put_object(
            Bucket=self.cfg.lineage_ingress_bucket_name,
            Key=key,
            Body=json.dumps(record).encode("utf-8"),
            ContentType="application/json",
        )
        return record

    def _table_bucket_arn(self) -> str:
        region = self.cfg.region
        account_id = make_session(self.cfg).client("sts").get_caller_identity()["Account"]
        return f"arn:aws:s3tables:{region}:{account_id}:bucket/{self.cfg.table_bucket_name}"
