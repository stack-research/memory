from __future__ import annotations

import json
import os
import time
from typing import Any, Protocol

from src.aws_session import make_session
from src.config import AwsConfig


class LineageReader(Protocol):
    def query_events(self, *, stream_id: str) -> list[dict[str, Any]]: ...


class _AthenaLineageReaderBase:
    def __init__(self, cfg: AwsConfig, *, catalog: str, database: str, table: str) -> None:
        self.cfg = cfg
        self.catalog = catalog
        self.database = database
        self.table = table
        self.athena = make_session(cfg).client("athena")

    def query_events(self, *, stream_id: str) -> list[dict[str, Any]]:
        sql = (
            "SELECT memory_id, event_type, payload, event_time "
            f"FROM {self.table} "
            f"WHERE stream_id = '{stream_id}' "
            "ORDER BY event_time"
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
                rows.append(
                    {
                        "memory_id": data[0].get("VarCharValue", ""),
                        "event_type": data[1].get("VarCharValue", ""),
                        "payload": json.loads(payload_raw) if payload_raw else {},
                        "event_time": data[3].get("VarCharValue", ""),
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
