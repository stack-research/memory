from __future__ import annotations

from src.bootstrap import ensure_lineage_bootstrap
from src.config import load_config
from src.ingestion.athena_ingestion import AthenaLineageIngestionJob
from src.storage import LineageStorage


if __name__ == "__main__":
    cfg = load_config()
    ensure_lineage_bootstrap(LineageStorage(cfg))
    result = AthenaLineageIngestionJob(cfg).run_once()
    print(result)
