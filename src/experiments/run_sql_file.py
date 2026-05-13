from __future__ import annotations

import argparse
import time
from pathlib import Path

from src.aws_session import make_session
from src.config import load_config


def _parse_statements(sql_text: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []

    for raw_line in sql_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("--"):
            continue
        current.append(raw_line)
        if line.endswith(";"):
            statement = "\n".join(current).strip()
            if statement.endswith(";"):
                statement = statement[:-1]
            if statement:
                statements.append(statement)
            current = []

    tail = "\n".join(current).strip()
    if tail:
        statements.append(tail)

    return statements


def _wait(athena, query_execution_id: str) -> str:
    while True:
        resp = athena.get_query_execution(QueryExecutionId=query_execution_id)
        state = resp["QueryExecution"]["Status"]["State"]
        if state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return state
        time.sleep(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sql_file")
    parser.add_argument("--database", default="memory_lab")
    parser.add_argument("--catalog", default="")
    parser.add_argument("--workgroup", default="memory-lab")
    args = parser.parse_args()

    cfg = load_config()
    athena = make_session(cfg).client("athena")
    sql_text = Path(args.sql_file).read_text(encoding="utf-8")
    statements = _parse_statements(sql_text)

    catalog = args.catalog or cfg.athena_s3tables_catalog

    for idx, statement in enumerate(statements, start=1):
        start = athena.start_query_execution(
            QueryString=statement,
            WorkGroup=args.workgroup,
            QueryExecutionContext={"Database": args.database, "Catalog": catalog},
        )
        qid = start["QueryExecutionId"]
        state = _wait(athena, qid)
        meta = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]
        result_location = meta.get("ResultConfiguration", {}).get("OutputLocation", "")
        console_link = (
            f"https://{cfg.region}.console.aws.amazon.com/athena/home?region={cfg.region}"
            f"#query/history/{qid}"
        )
        print(
            {
                "statement_index": idx,
                "state": state,
                "query_execution_id": qid,
                "result_location": result_location,
                "console_link": console_link,
            }
        )
        if state != "SUCCEEDED":
            break


if __name__ == "__main__":
    main()
