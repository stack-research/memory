from __future__ import annotations

import math
from hashlib import sha256


def embed_text(text: str, dims: int = 16) -> list[float]:
    """Deterministic embedding for experiments."""
    digest = sha256(text.encode("utf-8")).digest()
    values = [digest[i] / 255.0 for i in range(dims)]
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    size = min(len(a), len(b))
    return sum(a[i] * b[i] for i in range(size))
