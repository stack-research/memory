from __future__ import annotations

from src.storage import LineageStorage



def ensure_lineage_bootstrap(storage: LineageStorage) -> None:
    storage.ensure_namespace()
    storage.ensure_table()
