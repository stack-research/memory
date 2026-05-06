from __future__ import annotations

import json
import shutil
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from memory_lab.audit import AuditAPI
from memory_lab.config import Settings, load_dotenv
from memory_lab.service import MemoryLabService


def reset_lab(root: Path) -> None:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)


def run_e1(service: MemoryLabService) -> dict:
    service.ingest_event(
        memory_id="m_true_low_trust",
        sequence=1,
        event_type="observed",
        payload={"claim": "The sky is blue.", "trust_score": 0.2, "confidence": 0.9},
        source="weak_sensor",
    )
    service.ingest_event(
        memory_id="m_false_high_trust",
        sequence=1,
        event_type="observed",
        payload={"claim": "The sky is green.", "trust_score": 0.9, "confidence": 0.8},
        source="trusted_false_source",
    )
    selected = service.retrieve("What color is the sky?")
    return {"selected": selected}


def run_e4(service: MemoryLabService) -> dict:
    service.ingest_event(
        memory_id="m_true_low_trust",
        sequence=2,
        event_type="contradicted",
        payload={"target_memory_id": "m_false_high_trust"},
        source="conflict_worker",
    )
    service.ingest_event(
        memory_id="m_false_high_trust",
        sequence=2,
        event_type="contradicted",
        payload={"target_memory_id": "m_true_low_trust"},
        source="conflict_worker",
    )
    audit = AuditAPI(service.root)
    return {"lineage_true": audit.memory_lineage("m_true_low_trust")}


def run_e6(service: MemoryLabService) -> dict:
    service.ingest_event(
        memory_id="m_false_high_trust",
        sequence=3,
        event_type="quarantined",
        payload={"reason": "poisoning signal spike"},
        source="poison_worker",
    )
    selected = service.retrieve("What color is the sky?")
    return {"selected_after_quarantine": selected}


def run_e7(service: MemoryLabService) -> dict:
    replay_ok = service.replay_verify()
    compact_paths = service.compact()
    return {"replay_ok": replay_ok, "compaction_outputs": compact_paths}


def main() -> None:
    load_dotenv()
    settings = Settings.from_env()
    root = Path(settings.memory_root)
    reset_lab(root)
    service = MemoryLabService(root, settings=settings)
    results = {
        "E1": run_e1(service),
        "E4": run_e4(service),
        "E6": run_e6(service),
        "E7": run_e7(service),
    }
    out_path = Path("var/reports/baseline_report.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Wrote report: {out_path}")


if __name__ == "__main__":
    main()
