from __future__ import annotations

import json

from src.config import load_config
from src.ingestion.athena_ingestion import AthenaLineageIngestionJob


def main() -> None:
    cfg = load_config()
    job = AthenaLineageIngestionJob(cfg)

    target_db, target_table = job._split_target_table_fqn()
    target_columns = job._target_table_columns(
        catalog=cfg.athena_s3tables_catalog,
        database=target_db,
        table=target_table,
    )
    expected_columns = [
        "event_id",
        "agent_id",
        "stream_id",
        "event_type",
        "memory_id",
        "payload",
        "actor_class",
        "source_class",
        "event_time",
        "schema_version",
        "parent_event_id",
    ]
    projection = (
        "event_id,agent_id,stream_id,event_type,memory_id,payload,"
        "actor_class,source_class,CAST(from_iso8601_timestamp(event_time) AS timestamp) AS event_time,"
        "schema_version,parent_event_id"
    )

    status = "OK" if target_columns == expected_columns else "MISMATCH"
    print(
        json.dumps(
            {
                "preflight": status,
                "target_catalog": cfg.athena_s3tables_catalog,
                "target_database": target_db,
                "target_table": target_table,
                "target_columns": target_columns,
                "expected_columns": expected_columns,
                "insert_projection": projection,
            }
        )
    )
    if status != "OK":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
