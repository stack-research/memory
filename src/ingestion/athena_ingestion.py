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
        metrics = {
            "processed_count": 0,
            "canonical_inserted_count": 0,
            "quarantined_count": 0,
            "failed_statements": 0,
        }

        for step in self._build_statement_plan():
            qid = self._start(
                step["statement"],
                database=step["database"],
                catalog=step["catalog"],
            )
            state = self._wait(qid)
            step_result = {
                "query_execution_id": qid,
                "state": state,
                "statement": step["statement"],
                "database": step["database"],
                "catalog": step["catalog"],
                "name": step["name"],
            }

            if state == "SUCCEEDED":
                if step["name"] == "count_valid_rows":
                    metrics["processed_count"] = self._get_scalar_count(qid)
                    step_result["count"] = metrics["processed_count"]
                elif step["name"] == "insert_canonical":
                    metrics["canonical_inserted_count"] = self._get_update_count(qid)
                    step_result["update_count"] = metrics["canonical_inserted_count"]
                elif step["name"] == "insert_quarantine":
                    metrics["quarantined_count"] = self._get_update_count(qid)
                    step_result["update_count"] = metrics["quarantined_count"]
            else:
                metrics["failed_statements"] += 1

            statement_results.append(step_result)
            if state != "SUCCEEDED":
                return {"state": "FAILED", "metrics": metrics, "statements": statement_results}

        return {"state": "SUCCEEDED", "metrics": metrics, "statements": statement_results}

    def _start(self, statement: str, *, database: str, catalog: str) -> str:
        resp = self.athena.start_query_execution(
            QueryString=statement,
            WorkGroup=self._workgroup(),
            QueryExecutionContext={
                "Database": database,
                "Catalog": catalog,
            },
        )
        return resp["QueryExecutionId"]

    def _build_statement_plan(self) -> list[dict[str, str]]:
        raw_table = self._raw_table()
        quarantine_table = self._quarantine_table()
        target_database, target_table = self._split_target_table_fqn()
        source_catalog = self._catalog()
        source_database = self._database()
        source_raw_ref = f'"{source_catalog}"."{source_database}"."{raw_table}"'
        ingress_prefix = self.cfg.lineage_ingress_prefix.rstrip("/")
        ingress_path = f"s3://{self.cfg.lineage_ingress_bucket_name}/{ingress_prefix}/"

        quarantine_path = (
            f"s3://{self.cfg.lineage_ingress_bucket_name}/"
            f"{self.cfg.lineage_ingress_prefix.rstrip('/')}-quarantine/"
        )

        # v6 validation per TAI_TIMEKEEPING spec §4, §5.1, §6.
        # physical_moment is now a load-bearing JSON column; Tier 1a fields
        # must be extractable and non-null.
        pm = "json_extract(physical_moment, '$')"
        pm_tai_iso = "json_extract_scalar(physical_moment, '$.tai_iso')"
        pm_solar_age = "json_extract_scalar(physical_moment, '$.solar_age_myr')"
        pm_lon = "json_extract_scalar(physical_moment, '$.ecliptic_lon_deg')"
        pm_seq = "json_extract_scalar(physical_moment, '$.sequence_in_stream')"
        pm_hlc = "json_extract_scalar(physical_moment, '$.hlc_timestamp')"
        pm_hlc_eligible = "json_extract_scalar(physical_moment, '$.hlc_signature_eligible')"
        pm_tcid = "json_extract_scalar(physical_moment, '$.time_context_id')"

        valid_rows_predicate = (
            "event_id IS NOT NULL "
            "AND agent_id IS NOT NULL "
            "AND event_type IS NOT NULL "
            "AND memory_id IS NOT NULL "
            "AND actor_class IS NOT NULL "
            "AND source_class IS NOT NULL "
            "AND schema_version = '6.0' "
            "AND physical_moment IS NOT NULL "
            f"AND {pm_tai_iso} IS NOT NULL "
            f"AND try(from_iso8601_timestamp({pm_tai_iso})) IS NOT NULL "
            f"AND {pm_solar_age} IS NOT NULL "
            f"AND {pm_lon} IS NOT NULL "
            f"AND {pm_seq} IS NOT NULL "
            f"AND {pm_hlc} IS NOT NULL "
            f"AND {pm_tcid} IS NOT NULL"
        )

        return [
            {
                "name": "drop_raw_table",
                "database": source_database,
                "catalog": source_catalog,
                "statement": f"DROP TABLE IF EXISTS {raw_table}",
            },
            {
                "name": "create_raw_table",
                "database": source_database,
                "catalog": source_catalog,
                "statement": (
                    "CREATE EXTERNAL TABLE IF NOT EXISTS "
                    f"{raw_table} ("
                    "event_id string,"
                    "event_type string,"
                    "agent_id string,"
                    "stream_id string,"
                    "memory_id string,"
                    "event_time string,"
                    "schema_version string,"
                    "parent_event_id string,"
                    "actor_class string,"
                    "source_class string,"
                    "payload string,"
                    "physical_moment string"
                    ") "
                    "ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe' "
                    f"LOCATION '{ingress_path}'"
                ),
            },
            {
                "name": "create_quarantine_table",
                "database": source_database,
                "catalog": source_catalog,
                "statement": (
                    "CREATE EXTERNAL TABLE IF NOT EXISTS "
                    f"{quarantine_table} ("
                    "raw_event string,"
                    "reason string,"
                    "ingested_at timestamp"
                    ") "
                    "STORED AS PARQUET "
                    f"LOCATION '{quarantine_path}'"
                ),
            },
            {
                "name": "count_valid_rows",
                "database": source_database,
                "catalog": source_catalog,
                "statement": (
                    "SELECT count(*) "
                    f"FROM {raw_table} "
                    f"WHERE {valid_rows_predicate}"
                ),
            },
            {
                "name": "insert_canonical",
                "database": target_database,
                "catalog": self.cfg.athena_s3tables_catalog,
                "statement": (
                    "INSERT INTO "
                    f"{target_table} "
                    "SELECT "
                    "event_id,"
                    "event_type,"
                    "agent_id,"
                    "stream_id,"
                    "memory_id,"
                    "payload,"
                    "actor_class,"
                    "source_class,"
                    "schema_version,"
                    "parent_event_id,"
                    "physical_moment,"
                    f"{pm_tai_iso} AS pm_tai_iso,"
                    f"CAST({pm_solar_age} AS double) AS pm_solar_age_myr,"
                    f"CAST({pm_lon} AS double) AS pm_ecliptic_lon_deg,"
                    f"CAST({pm_seq} AS bigint) AS pm_sequence_in_stream,"
                    f"{pm_hlc} AS pm_hlc_timestamp,"
                    f"COALESCE(try(CAST({pm_hlc_eligible} AS boolean)), TRUE) AS pm_hlc_signature_eligible,"
                    f"{pm_tcid} AS pm_time_context_id "
                    f"FROM {source_raw_ref} r "
                    f"WHERE {valid_rows_predicate} "
                    "AND NOT EXISTS ("
                    "SELECT 1 FROM "
                    f"{target_table} t "
                    "WHERE t.event_id = r.event_id"
                    ")"
                ),
            },
            {
                "name": "insert_quarantine",
                "database": source_database,
                "catalog": source_catalog,
                "statement": (
                    "INSERT INTO "
                    f"{quarantine_table} "
                    "SELECT "
                    "json_format(CAST(row(event_id, event_type, agent_id, stream_id, memory_id, event_time, schema_version, parent_event_id, actor_class, source_class, payload, physical_moment) AS JSON)),"
                    "CASE "
                    "WHEN event_id IS NULL OR agent_id IS NULL OR event_type IS NULL OR memory_id IS NULL OR schema_version IS NULL OR actor_class IS NULL OR source_class IS NULL THEN 'missing_required_field' "
                    "WHEN schema_version <> '6.0' THEN 'unsupported_schema_version' "
                    "WHEN physical_moment IS NULL THEN 'missing_physical_moment' "
                    f"WHEN {pm_tai_iso} IS NULL THEN 'missing_physical_moment' "
                    f"WHEN try(from_iso8601_timestamp({pm_tai_iso})) IS NULL THEN 'invalid_tai_iso' "
                    f"WHEN {pm_solar_age} IS NULL OR {pm_lon} IS NULL OR {pm_seq} IS NULL OR {pm_hlc} IS NULL THEN 'missing_physical_moment' "
                    f"WHEN {pm_tcid} IS NULL THEN 'dangling_time_context_id' "
                    "ELSE 'unknown_validation_failure' END,"
                    "current_timestamp "
                    f"FROM {raw_table} "
                    "WHERE event_id IS NULL "
                    "OR agent_id IS NULL "
                    "OR event_type IS NULL "
                    "OR memory_id IS NULL "
                    "OR schema_version IS NULL "
                    "OR actor_class IS NULL "
                    "OR source_class IS NULL "
                    "OR schema_version <> '6.0' "
                    "OR physical_moment IS NULL "
                    f"OR {pm_tai_iso} IS NULL "
                    f"OR try(from_iso8601_timestamp({pm_tai_iso})) IS NULL "
                    f"OR {pm_solar_age} IS NULL "
                    f"OR {pm_lon} IS NULL "
                    f"OR {pm_seq} IS NULL "
                    f"OR {pm_hlc} IS NULL "
                    f"OR {pm_tcid} IS NULL"
                ),
            },
        ]

    def _split_target_table_fqn(self) -> tuple[str, str]:
        target_table_fqn = self._target_table_fqn()
        parts = target_table_fqn.split(".", 1)
        if len(parts) != 2:
            raise ValueError(
                "AWS_ATHENA_TARGET_TABLE_FQN must be in 'database.table' format; "
                f"got '{target_table_fqn}'"
            )
        return parts[0], parts[1]

    def _target_table_columns(self, *, catalog: str, database: str, table: str) -> list[str]:
        qid = self._start(
            (
                "SELECT column_name "
                "FROM information_schema.columns "
                f"WHERE table_schema = '{database}' "
                f"AND table_name = '{table}' "
                "ORDER BY ordinal_position"
            ),
            database="information_schema",
            catalog=catalog,
        )
        state = self._wait(qid)
        if state != "SUCCEEDED":
            raise RuntimeError(f"Failed to inspect target table schema: {catalog}.{database}.{table}")

        resp = self.athena.get_query_results(QueryExecutionId=qid)
        rows = resp.get("ResultSet", {}).get("Rows", [])
        columns: list[str] = []
        for row in rows[1:]:
            data = row.get("Data", [])
            if not data:
                continue
            value = data[0].get("VarCharValue")
            if value:
                columns.append(value)
        if not columns:
            raise RuntimeError(f"No columns found for target table: {catalog}.{database}.{table}")
        return columns

    def _wait(self, query_execution_id: str) -> str:
        while True:
            resp = self.athena.get_query_execution(QueryExecutionId=query_execution_id)
            state = resp["QueryExecution"]["Status"]["State"]
            if state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                return state
            time.sleep(2)

    def _get_update_count(self, query_execution_id: str) -> int:
        resp = self.athena.get_query_results(QueryExecutionId=query_execution_id)
        return int(resp.get("UpdateCount", 0))

    def _get_scalar_count(self, query_execution_id: str) -> int:
        resp = self.athena.get_query_results(QueryExecutionId=query_execution_id)
        rows = resp.get("ResultSet", {}).get("Rows", [])
        if len(rows) < 2:
            return 0
        data = rows[1].get("Data", [])
        if not data:
            return 0
        return int(data[0].get("VarCharValue", "0"))

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

        return os.environ.get("AWS_ATHENA_TARGET_TABLE_FQN", "memory_lab.memory_events_v6")
