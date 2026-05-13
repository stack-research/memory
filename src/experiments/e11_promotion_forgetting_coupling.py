from __future__ import annotations

from src.config import load_config
from src.embeddings import BedrockEmbeddings
from src.lineage_engine import LineageEngine
from src.storage import LineageStorage
from src.vectors import RecallVectors


def _share(rows: list[dict], *, kind: str, k: int = 5) -> float:
    top = rows[:k]
    if not top:
        return 0.0
    n = sum(1 for row in top if row.get("metadata", {}).get("kind") == kind)
    return n / len(top)


def run() -> dict:
    cfg = load_config()
    storage = LineageStorage(cfg)
    vectors = RecallVectors(cfg)
    embedder = BedrockEmbeddings(cfg)
    lineage = LineageEngine(storage)

    agent_id = "lab-agent-1"
    stream_id = "exp-e11"
    vectors.set_lineage_context(lineage=lineage, agent_id=agent_id, stream_id=stream_id)

    promotion_threshold_k = 8
    promotion_threshold_epsilon = 0.2

    clusters = [
        {
            "cluster_id": "invoice-reminders",
            "episodic_ids": ["mem-e11-ep-1", "mem-e11-ep-2", "mem-e11-ep-3", "mem-e11-ep-4"],
            "claims": [
                "User asked for monthly invoice reminders.",
                "User enabled reminder notifications after a missed invoice.",
                "User confirmed reminders reduce late payments.",
                "Support set reminders enabled by default.",
            ],
            "access_count": 14,
            "context_variance": 0.1,
            "expected_promote": True,
        },
        {
            "cluster_id": "shipping-preferences-noisy",
            "episodic_ids": ["mem-e11-ep-5", "mem-e11-ep-6", "mem-e11-ep-7"],
            "claims": [
                "User asked for overnight shipping.",
                "User asked for economy shipping.",
                "User asked for pickup in store.",
            ],
            "access_count": 6,
            "context_variance": 0.67,
            "expected_promote": False,
        },
    ]

    for cluster in clusters:
        for memory_id, claim in zip(cluster["episodic_ids"], cluster["claims"]):
            vectors.put_memory_vector(
                key=memory_id,
                vector=embedder.embed_text(claim),
                metadata={
                    "agent_id": agent_id,
                    "stream_id": stream_id,
                    "kind": "episodic",
                    "status": "active",
                    "cluster_id": cluster["cluster_id"],
                    "source_trust": 0.75,
                    "reinforcement": 1.1,
                    "safety": 1.0,
                },
            )
            lineage.emit(
                event_type="observed",
                agent_id=agent_id,
                stream_id=stream_id,
                memory_id=memory_id,
                payload={"claim": claim, "cluster_id": cluster["cluster_id"], "kind": "episodic"},
            )

    query = "What stable customer preference should influence billing communication defaults?"
    query_vec = embedder.embed_text(query)
    before_probe = vectors.query(vector=query_vec, top_k=10, agent_id=agent_id, stream_id=stream_id)
    before_rows = before_probe.get("vectors", [])

    tp = 0
    fp = 0
    promoted_clusters: list[str] = []

    for cluster in clusters:
        promote = (
            cluster["access_count"] > promotion_threshold_k
            and cluster["context_variance"] < promotion_threshold_epsilon
        )

        if promote and cluster["expected_promote"]:
            tp += 1
        if promote and not cluster["expected_promote"]:
            fp += 1

        lineage.emit(
            event_type="snapshotted",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=f"e11-gate-{cluster['cluster_id']}",
            payload={
                "snapshot_type": "promotion_gate",
                "cluster_id": cluster["cluster_id"],
                "access_count": cluster["access_count"],
                "context_variance": cluster["context_variance"],
                "promotion_eligible": promote,
                "expected_promote": cluster["expected_promote"],
            },
        )

        if not promote:
            continue

        promoted_clusters.append(cluster["cluster_id"])
        semantic_id = f"mem-e11-sem-{cluster['cluster_id']}"
        semantic_claim = "User prefers monthly invoice reminders to avoid late payments."
        vectors.put_memory_vector(
            key=semantic_id,
            vector=embedder.embed_text(semantic_claim),
            metadata={
                "agent_id": agent_id,
                "stream_id": stream_id,
                "kind": "semantic",
                "status": "active",
                "cluster_id": cluster["cluster_id"],
                "source_trust": 0.8,
                "reinforcement": 2.2,
                "safety": 1.0,
            },
        )

        promoted_event = lineage.emit(
            event_type="promoted",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=semantic_id,
            payload={
                "claim": semantic_claim,
                "cluster_id": cluster["cluster_id"],
                "derived_from": cluster["episodic_ids"],
            },
        )

        for episodic_id, claim in zip(cluster["episodic_ids"], cluster["claims"]):
            vectors.put_memory_vector(
                key=episodic_id,
                vector=embedder.embed_text(claim),
                metadata={
                    "agent_id": agent_id,
                    "stream_id": stream_id,
                    "kind": "episodic",
                    "status": "suppressed",
                    "cluster_id": cluster["cluster_id"],
                    "source_trust": 0.75,
                    "reinforcement": 0.7,
                    "safety": 0.6,
                },
            )
            lineage.emit(
                event_type="mutated",
                agent_id=agent_id,
                stream_id=stream_id,
                memory_id=episodic_id,
                parent_event_id=promoted_event.event_id,
                payload={
                    "cluster_id": cluster["cluster_id"],
                    "relation": "derived_from",
                    "promotion_link": semantic_id,
                    "status_after": "suppressed",
                },
            )

    after_probe = vectors.query(vector=query_vec, top_k=10, agent_id=agent_id, stream_id=stream_id)
    after_rows = after_probe.get("vectors", [])

    episodic_before = _share(before_rows, kind="episodic", k=5)
    episodic_after = _share(after_rows, kind="episodic", k=5)
    semantic_before = _share(before_rows, kind="semantic", k=5)
    semantic_after = _share(after_rows, kind="semantic", k=5)

    episodic_drop_ratio = (episodic_before - episodic_after) / episodic_before if episodic_before > 0 else 0.0
    semantic_gain = semantic_after - semantic_before

    predicted_positive = len(promoted_clusters)
    promotion_precision = tp / predicted_positive if predicted_positive > 0 else 1.0

    summary = {
        "stream_id": stream_id,
        "promoted_clusters": promoted_clusters,
        "promotion_precision": promotion_precision,
        "episodic_before_top5_share": episodic_before,
        "episodic_after_top5_share": episodic_after,
        "semantic_before_top5_share": semantic_before,
        "semantic_after_top5_share": semantic_after,
        "episodic_drop_ratio": episodic_drop_ratio,
        "semantic_gain": semantic_gain,
        "pass_precision": promotion_precision >= 0.8,
        "pass_shift": episodic_drop_ratio >= 0.3 and semantic_gain >= 0.2,
        "pass": (promotion_precision >= 0.8) and (episodic_drop_ratio >= 0.3 and semantic_gain >= 0.2),
        "false_positives": fp,
    }

    lineage.emit(
        event_type="snapshotted",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id="e11-summary",
        payload={
            "snapshot_type": "promotion_forgetting_coupling",
            "snapshot_stage": "final",
            **summary,
            **cfg.retrieval_policy.audit_fields(),
        },
    )

    print(summary)
    return summary


if __name__ == "__main__":
    run()
