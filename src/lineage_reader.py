from __future__ import annotations

import json
import os
import time
from typing import Any, Protocol

from src.aws_session import make_session
from src.config import AwsConfig


class LineageReader(Protocol):
    def query_events(self, *, stream_id: str) -> list[dict[str, Any]]: ...

    def query_memory_events(
        self,
        *,
        stream_id: str,
        memory_id: str,
        as_of_time: str | None = None,
    ) -> list[dict[str, Any]]: ...


class _AthenaLineageReaderBase:
    def __init__(self, cfg: AwsConfig, *, catalog: str, database: str, table: str) -> None:
        self.cfg = cfg
        self.catalog = catalog
        self.database = database
        self.table = table
        self.athena = make_session(cfg).client("athena")

    def query_events(self, *, stream_id: str) -> list[dict[str, Any]]:
        # v7 EPISTEMIC_TRIANGLE §8.1 single-stream canonical order:
        # (pm_tai_iso, pm_sequence_in_stream, event_id). Returned
        # rows include `event_time` keyed off pm_tai_iso so legacy
        # callers continue to work.
        sql = (
            "SELECT memory_id, event_type, payload, pm_tai_iso "
            f"FROM {self.table} "
            f"WHERE stream_id = '{stream_id}' "
            "ORDER BY pm_tai_iso, pm_sequence_in_stream, event_id"
        )
        start = self.athena.start_query_execution(
            QueryString=sql,
            WorkGroup=os.environ.get("AWS_ATHENA_WORKGROUP_NAME", "memory-lab"),
            QueryExecutionContext={"Database": self.database, "Catalog": self.catalog},
        )
        qid = start["QueryExecutionId"]
        state = self._wait_for_query(qid)
        if state != "SUCCEEDED":
            raise RuntimeError(f"Athena query failed: {qid} state={state}")

        rows: list[dict[str, Any]] = []
        paginator = self.athena.get_paginator("get_query_results")
        for page in paginator.paginate(QueryExecutionId=qid):
            for row in page["ResultSet"]["Rows"]:
                data = row.get("Data", [])
                if len(data) < 4:
                    continue
                if data[0].get("VarCharValue") == "memory_id":
                    continue
                payload_raw = data[2].get("VarCharValue", "{}")
                pm_tai_iso = data[3].get("VarCharValue", "")
                rows.append(
                    {
                        "memory_id": data[0].get("VarCharValue", ""),
                        "event_type": data[1].get("VarCharValue", ""),
                        "payload": json.loads(payload_raw) if payload_raw else {},
                        "pm_tai_iso": pm_tai_iso,
                        # event_time is a v6 alias kept for legacy
                        # callers; v7 anchor is pm_tai_iso.
                        "event_time": pm_tai_iso,
                    }
                )
        return rows

    def query_memory_events(
        self,
        *,
        stream_id: str,
        memory_id: str,
        as_of_time: str | None = None,
    ) -> list[dict[str, Any]]:
        # v7 EPISTEMIC_TRIANGLE §8.1: anchor on pm_tai_iso; per-stream
        # ordering uses (pm_tai_iso, pm_sequence_in_stream, event_id).
        # pm_tai_iso is a STRING column (TAI ISO is lexicographically
        # ordered for the supported precision), so compare strings —
        # casting to TIMESTAMP would mismatch and Athena would error.
        where_time = (
            f"AND pm_tai_iso <= '{as_of_time}'" if as_of_time else ""
        )
        sql = (
            "SELECT event_id, parent_event_id, source_class, pm_tai_iso, pm_sequence_in_stream "
            f"FROM {self.table} "
            f"WHERE stream_id = '{stream_id}' "
            f"AND memory_id = '{memory_id}' "
            f"{where_time} "
            "ORDER BY pm_tai_iso, pm_sequence_in_stream, event_id"
        )
        start = self.athena.start_query_execution(
            QueryString=sql,
            WorkGroup=os.environ.get("AWS_ATHENA_WORKGROUP_NAME", "memory-lab"),
            QueryExecutionContext={"Database": self.database, "Catalog": self.catalog},
        )
        qid = start["QueryExecutionId"]
        state = self._wait_for_query(qid)
        if state != "SUCCEEDED":
            raise RuntimeError(f"Athena query failed: {qid} state={state}")

        rows: list[dict[str, Any]] = []
        paginator = self.athena.get_paginator("get_query_results")
        for page in paginator.paginate(QueryExecutionId=qid):
            for row in page["ResultSet"]["Rows"]:
                data = row.get("Data", [])
                if len(data) < 5:
                    continue
                if data[0].get("VarCharValue") == "event_id":
                    continue
                pm_tai_iso = data[3].get("VarCharValue", "")
                pm_seq_raw = data[4].get("VarCharValue", "")
                try:
                    pm_seq = int(pm_seq_raw) if pm_seq_raw else None
                except (TypeError, ValueError):
                    pm_seq = None
                rows.append(
                    {
                        "event_id": data[0].get("VarCharValue", ""),
                        "parent_event_id": data[1].get("VarCharValue") or None,
                        "source_class": data[2].get("VarCharValue") or "unknown",
                        "pm_tai_iso": pm_tai_iso,
                        "pm_sequence_in_stream": pm_seq,
                        # event_time alias for v6 callers; v7 anchor
                        # is pm_tai_iso.
                        "event_time": pm_tai_iso,
                    }
                )
        return rows

    def _wait_for_query(self, query_execution_id: str) -> str:
        while True:
            resp = self.athena.get_query_execution(QueryExecutionId=query_execution_id)
            state = resp["QueryExecution"]["Status"]["State"]
            if state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                return state
            time.sleep(1)


class AthenaCanonicalReader(_AthenaLineageReaderBase):
    def __init__(self, cfg: AwsConfig) -> None:
        database, table = cfg.athena_target_table_fqn.split(".", 1)
        super().__init__(cfg, catalog="AwsDataCatalog", database=database, table=table)


class S3TablesCanonicalReader(_AthenaLineageReaderBase):
    def __init__(self, cfg: AwsConfig) -> None:
        database, table = cfg.athena_target_table_fqn.split(".", 1)
        super().__init__(
            cfg,
            catalog=cfg.athena_s3tables_catalog,
            database=database,
            table=table,
        )


def build_lineage_reader(cfg: AwsConfig) -> LineageReader:
    backend = os.environ.get("AWS_LINEAGE_READER_BACKEND", "s3tables").strip().lower()
    if backend == "athena":
        return AthenaCanonicalReader(cfg)
    if backend == "s3tables":
        return S3TablesCanonicalReader(cfg)
    raise ValueError(
        "AWS_LINEAGE_READER_BACKEND must be one of: athena, s3tables; "
        f"got '{backend}'"
    )
