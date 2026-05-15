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
    # v7 EPISTEMIC_TRIANGLE §9.2 schema. event_time is removed;
    # pm_tai_iso is the canonical anchor. record_kind /
    # assertion_kind / subject_* are denormalized hot columns.
    #
    # Column ORDER must match the CDK stack's `LineageTable` schema
    # because Athena `INSERT INTO target SELECT ...` is positional.
    # Drift between CDK column order and this expected list will
    # silently swap field values at INSERT time.
    expected_columns = [
        "event_id",
        "event_type",
        "agent_id",
        "stream_id",
        "memory_id",
        "payload",
        "actor_class",
        "source_class",
        "schema_version",
        "parent_event_id",
        "physical_moment",
        "pm_tai_iso",
        "pm_solar_age_myr",
        "pm_ecliptic_lon_deg",
        "pm_sequence_in_stream",
        "pm_hlc_timestamp",
        "pm_hlc_signature_eligible",
        "pm_time_context_id",
        "record_kind",
        "assertion_kind",
        "subject_event_id",
        "subject_record_kind",
        "subject_assertion_kind",
    ]
    # Mirror the projection that
    # `AthenaLineageIngestionJob._build_statement_plan` emits in
    # the canonical INSERT. Column ORDER and EXTRACTION shape must
    # match — Athena INSERT is positional. Drifting the printed
    # projection silently misleads anyone diffing it against the
    # real ingestion SQL. Cross-substrate review caught this gap.
    projection = (
        "event_id,event_type,agent_id,stream_id,memory_id,payload,"
        "actor_class,source_class,schema_version,parent_event_id,"
        "physical_moment,"
        "json_extract_scalar(physical_moment, '$.tai_iso') AS pm_tai_iso,"
        "CAST(json_extract_scalar(physical_moment, '$.solar_age_myr') AS double) AS pm_solar_age_myr,"
        "CAST(json_extract_scalar(physical_moment, '$.ecliptic_lon_deg') AS double) AS pm_ecliptic_lon_deg,"
        "CAST(json_extract_scalar(physical_moment, '$.sequence_in_stream') AS bigint) AS pm_sequence_in_stream,"
        "json_extract_scalar(physical_moment, '$.hlc_timestamp') AS pm_hlc_timestamp,"
        "COALESCE(try(CAST(json_extract_scalar(physical_moment, '$.hlc_signature_eligible') AS boolean)), TRUE) AS pm_hlc_signature_eligible,"
        "json_extract_scalar(physical_moment, '$.time_context_id') AS pm_time_context_id,"
        "record_kind,assertion_kind,subject_event_id,subject_record_kind,subject_assertion_kind"
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
