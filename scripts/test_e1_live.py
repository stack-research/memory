from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib.request import Request, urlopen


def call(method: str, url: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = Request(url=url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def assert_with_retry(fn, timeout_s: int = 45, interval_s: int = 3):
    deadline = time.time() + timeout_s
    last_exc = None
    while time.time() < deadline:
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            time.sleep(interval_s)
    if last_exc:
        raise last_exc
    raise TimeoutError("timed out without result")


def write_reports(ok: bool, details: dict) -> None:
    out_dir = Path("var/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "e1_live_test_results.json"
    json_path.write_text(json.dumps({"ok": ok, "details": details}, indent=2), encoding="utf-8")

    junit_path = out_dir / "e1_live_test_results.xml"
    status = "0" if ok else "1"
    failure_tag = "" if ok else f"<failure message=\"E1 live assertions failed\">{json.dumps(details)}</failure>"
    xml = (
        f"<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        f"<testsuite name=\"e1_live\" tests=\"1\" failures=\"{status}\">"
        f"<testcase classname=\"e1\" name=\"trust_vs_truth\">{failure_tag}</testcase>"
        f"</testsuite>"
    )
    junit_path.write_text(xml, encoding="utf-8")


def main() -> None:
    base_url = os.environ.get("MEMORY_API_BASE_URL")
    if not base_url:
        raise RuntimeError("MEMORY_API_BASE_URL is required")

    details = {}

    def checks():
        retrieve = call("POST", f"{base_url}/v1/retrieve", {"query": "What color is the sky?", "top_k": 5})
        details["retrieve"] = retrieve
        results = retrieve.get("results", [])
        if not results:
            raise AssertionError("retrieve results are empty")

        top_memory_id = results[0][0]
        details["top_memory_id"] = top_memory_id
        lineage = call("GET", f"{base_url}/v1/memory/{top_memory_id}/lineage").get("lineage", [])
        details["top_lineage_count"] = len(lineage)
        if not lineage:
            raise AssertionError("top memory lineage is empty")

        first = lineage[-1]
        if not first.get("event_id"):
            raise AssertionError("lineage missing event_id traceability")
        return True

    try:
        assert_with_retry(checks)
        write_reports(True, details)
        print("E1 live tests passed")
    except Exception as exc:
        details["error"] = str(exc)
        write_reports(False, details)
        raise


if __name__ == "__main__":
    main()
