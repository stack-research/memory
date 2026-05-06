from __future__ import annotations


def contradiction_flag(*, has_conflicts: bool) -> float:
    return 0.6 if has_conflicts else 1.0
