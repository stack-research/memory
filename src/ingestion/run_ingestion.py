from __future__ import annotations

from src.config import load_config
from src.ingestion.athena_ingestion import AthenaLineageIngestionJob


if __name__ == "__main__":
    result = AthenaLineageIngestionJob(load_config()).run_once()
    print(result)
