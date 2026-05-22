"""Control-plane cue ingestion — local consumer command.

Spec: specs/CONTROL_PLANE_INGEST.md §8.

Drains the `memory-lab.fifo` SQS queue and runs each message through
`CueIngestionConsumer` (capture-before-act). For the lab this is a
command you run by hand:

  PYTHONPATH=. uv run --project stacks python -m src.implicit_memory.run_cue_ingest --stream-id <id>

There is deliberately no auto-trigger in the lab — no Lambda event
source, no scheduled poller. The bus and queue may emit "new message"
events into a void; nothing reacts until this command is run. A
production deployment would host the consumer in a Lambda (spec §8);
the lab stops at this command.

SQS message handling:
  - a returned `IngestOutcome` (ingested / rejected / duplicate /
    routed_away) is terminal -> delete the message;
  - a `TransientIngestError` is a system fault -> leave the message;
    it redelivers after the visibility timeout and dead-letters after
    the queue's `max_receive_count`;
  - a body that will not JSON-decode is left for the DLQ — never
    silently dropped.

`routed_away` is deleted here because the lab runs a single worker;
a multi-worker deployment would instead leave a foreign-scope cue for
its owning worker. That is a production concern, out of lab scope.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from src.aws_session import make_session
from src.config import load_config
from src.cutover_v7 import build_time_context
from src.implicit_memory.cue_ingest import (
    CueIngestionConsumer,
    LineageBackedSeenCueStore,
    TransientIngestError,
    cue_from_message,
    declare_control_plane_event_types,
)
from src.lineage_engine import LineageEngine
from src.lineage_reader import build_lineage_reader
from src.storage import LineageStorage


_FIFO_QUEUE_NAME_DEFAULT = "memory-lab.fifo"


def cue_detail_from_body(body: str) -> dict[str, Any] | None:
    """Extract the cue body from an SQS message body.

    The message body is an EventBridge event; the cue is its `detail`
    (CONTROL_PLANE_INGEST Decision 2 — the EventBridge envelope).
    Returns None when the body is not JSON or carries no object
    `detail` — a transport-malformed message the caller leaves for the
    DLQ rather than dropping.
    """
    try:
        event = json.loads(body)
    except (ValueError, TypeError):
        return None
    if not isinstance(event, dict):
        return None
    detail = event.get("detail")
    return detail if isinstance(detail, dict) else None


def drain_queue(
    *,
    consumer: CueIngestionConsumer,
    sqs_client: Any,
    queue_url: str,
    max_batches: int = 1000,
) -> dict[str, int]:
    """Receive and process messages until the queue returns empty.

    Returns a summary count by outcome. A message is deleted only when
    `ingest` returns an outcome; a `TransientIngestError` or an
    unparseable body leaves the message on the queue.
    """
    counts: dict[str, int] = {
        "ingested": 0,
        "rejected": 0,
        "duplicate": 0,
        "routed_away": 0,
        "transient_left": 0,
        "malformed_transport_left": 0,
    }
    for _ in range(max_batches):
        resp = sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=1,
        )
        messages = resp.get("Messages", [])
        if not messages:
            break
        for msg in messages:
            detail = cue_detail_from_body(msg.get("Body", ""))
            if detail is None:
                # Transport-malformed — leave it on the queue; the DLQ
                # catches it after the redelivery budget.
                counts["malformed_transport_left"] += 1
                continue
            cue = cue_from_message(detail)
            try:
                outcome = consumer.ingest(cue)
            except TransientIngestError:
                # System fault — leave the message to redeliver / DLQ.
                counts["transient_left"] += 1
                continue
            # Terminal outcome — safe to delete.
            counts[outcome.status.value] = counts.get(outcome.status.value, 0) + 1
            sqs_client.delete_message(
                QueueUrl=queue_url, ReceiptHandle=msg["ReceiptHandle"]
            )
    return counts


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Control-plane cue ingestion consumer (lab command)"
    )
    p.add_argument("--agent-id", default="lab-agent-1")
    p.add_argument(
        "--stream-id",
        required=True,
        help="the worker's stream scope; cues for other scopes route away",
    )
    p.add_argument("--queue-name", default=_FIFO_QUEUE_NAME_DEFAULT)
    p.add_argument(
        "--declare-event-types",
        action="store_true",
        help="emit event_type_declared for the control-plane types once, then drain",
    )
    args = p.parse_args(argv)

    cfg = load_config()
    session = make_session(cfg)
    storage = LineageStorage(cfg)

    # build_time_context() is deterministic — this yields the same
    # time_context_id the v7 cutover declared, so captured cues are
    # emitted against the canonical table's active time context.
    _, time_context_id, _ = build_time_context()
    engine = LineageEngine(storage=storage, time_context_id=time_context_id)

    if args.declare_event_types:
        declare_control_plane_event_types(
            engine, agent_id=args.agent_id, stream_id="__canonical_meta__"
        )

    consumer = CueIngestionConsumer(
        lineage=engine,
        agent_id=args.agent_id,
        stream_id=args.stream_id,
        seen_cues=LineageBackedSeenCueStore(
            reader=build_lineage_reader(cfg), stream_id=args.stream_id
        ),
    )

    sqs = session.client("sqs")
    queue_url = sqs.get_queue_url(QueueName=args.queue_name)["QueueUrl"]
    summary = drain_queue(consumer=consumer, sqs_client=sqs, queue_url=queue_url)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
