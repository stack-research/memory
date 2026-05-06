from __future__ import annotations

import time

from src.aws_session import make_session
from src.config import AwsConfig


class AthenaLineageIngestionJob:
    def __init__(self, cfg: AwsConfig) -> None:
        self.cfg = cfg
        self.athena = make_session(cfg).client("athena")

    def run_once(self) -> dict:
        if not self.cfg.lineage_ingress_bucket_name:
            raise ValueError("AWS_S3_LINEAGE_INGRESS_BUCKET_NAME must be set")

        statement_results: list[dict] = []
        for statement in self._build_statements():
            qid = self._start(statement)
            state = self._wait(qid)
            statement_results.append(
                {
                    "query_execution_id": qid,
                    "state": state,
                    "statement": statement,
                }
            )
            if state != "SUCCEEDED":
                return {"state": "FAILED", "statements": statement_results}

        return {"state": "SUCCEEDED", "statements": statement_results}

    def _start(self, statement: str) -> str:
        resp = self.athena.start_query_execution(
            QueryString=statement,
            WorkGroup=self._workgroup(),
            QueryExecutionContext={
                "Database": self._database(),
                "Catalog": self._catalog(),
            },
        )
        return resp["QueryExecutionId"]

    def _build_statements(self) -> list[str]:
        raw_table = self._raw_table()
        quarantine_table = self._quarantine_table()
        target_table = self._target_table_fqn()
        ingress_prefix = self.cfg.lineage_ingress_prefix.rstrip("/")
        ingress_path = f"s3://{self.cfg.lineage_ingress_bucket_name}/{ingress_prefix}/"

        quarantine_path = (
            f"s3://{self.cfg.lineage_ingress_bucket_name}/"
            f"{self.cfg.lineage_ingress_prefix.rstrip('/')}/quarantine/"
        )

        target_path = (
            f"s3://{self.cfg.lineage_ingress_bucket_name}/"
            f"{self.cfg.lineage_ingress_prefix.rstrip('/')}/canonical/"
        )

        return [
            (
                "CREATE EXTERNAL TABLE IF NOT EXISTS "
                f"{raw_table} ("
                "event_id string,"
                "event_type string,"
                "agent_id string,"
                "stream_id string,"
                "memory_id string,"
                "event_time string,"
                "parent_event_id string,"
                "payload string"
                ") "
                "ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe' "
                f"LOCATION '{ingress_path}'"
            ),
            (
                "CREATE EXTERNAL TABLE IF NOT EXISTS "
                f"{quarantine_table} ("
                "raw_event string,"
                "reason string,"
                "ingested_at timestamp"
                ") "
                "STORED AS PARQUET "
                f"LOCATION '{quarantine_path}'"
            ),
            (
                "CREATE EXTERNAL TABLE IF NOT EXISTS "
                f"{target_table} ("
                "event_id string,"
                "agent_id string,"
                "stream_id string,"
                "event_type string,"
                "memory_id string,"
                "payload string,"
                "event_time timestamp,"
                "parent_event_id string"
                ") "
                "STORED AS PARQUET "
                f"LOCATION '{target_path}'"
            ),
            (
                "INSERT INTO "
                f"{target_table} "
                "SELECT "
                "event_id,"
                "agent_id,"
                "stream_id,"
                "event_type,"
                "memory_id,"
                "payload,"
                "from_iso8601_timestamp(event_time) AS event_time,"
                "parent_event_id "
                f"FROM {raw_table} "
                "WHERE event_id IS NOT NULL "
                "AND agent_id IS NOT NULL "
                "AND event_type IS NOT NULL "
                "AND memory_id IS NOT NULL "
                "AND event_time IS NOT NULL"
            ),
            (
                "INSERT INTO "
                f"{quarantine_table} "
                "SELECT "
                "json_format(CAST(row(event_id, event_type, agent_id, stream_id, memory_id, event_time, parent_event_id, payload) AS JSON)),"
                "'missing_required_field',"
                "current_timestamp "
                f"FROM {raw_table} "
                "WHERE event_id IS NULL "
                "OR agent_id IS NULL "
                "OR event_type IS NULL "
                "OR memory_id IS NULL "
                "OR event_time IS NULL"
            ),
        ]

    def _wait(self, query_execution_id: str) -> str:
        while True:
            resp = self.athena.get_query_execution(QueryExecutionId=query_execution_id)
            state = resp["QueryExecution"]["Status"]["State"]
            if state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                return state
            time.sleep(2)

    @staticmethod
    def _workgroup() -> str:
        import os

        return os.environ.get("AWS_ATHENA_WORKGROUP_NAME", "memory-lab")

    @staticmethod
    def _database() -> str:
        import os

        return os.environ.get("AWS_ATHENA_DATABASE", "memory_lab")

    @staticmethod
    def _catalog() -> str:
        import os

        return os.environ.get("AWS_ATHENA_CATALOG", "AwsDataCatalog")

    @staticmethod
    def _raw_table() -> str:
        import os

        return os.environ.get("AWS_ATHENA_RAW_EVENTS_TABLE", "lineage_events_raw")

    @staticmethod
    def _quarantine_table() -> str:
        import os

        return os.environ.get("AWS_ATHENA_QUARANTINE_TABLE", "lineage_events_quarantine")

    @staticmethod
    def _target_table_fqn() -> str:
        import os

        return os.environ.get(
            "AWS_ATHENA_TARGET_TABLE_FQN", "memory_lab.lineage_events_canonical"
        )
