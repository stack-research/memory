"""Focused checks for the first im_w consequence-loop binding.

Run from repo root:
  PYTHONPATH=. uv run --project stacks python -m src.experiments.implicit.im_w_consequence_verify
"""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from typing import Any, Iterator

from src.experiments.implicit import im_w_runtime_calibration as im_w


class _Cfg:
    pass


@contextmanager
def _prior_summary_uri(uri: str | None) -> Iterator[None]:
    old = os.environ.get("IMPLICIT_CALIBRATION_PRIOR_SUMMARY_URI")
    try:
        if uri is None:
            os.environ.pop("IMPLICIT_CALIBRATION_PRIOR_SUMMARY_URI", None)
        else:
            os.environ["IMPLICIT_CALIBRATION_PRIOR_SUMMARY_URI"] = uri
        yield
    finally:
        if old is None:
            os.environ.pop("IMPLICIT_CALIBRATION_PRIOR_SUMMARY_URI", None)
        else:
            os.environ["IMPLICIT_CALIBRATION_PRIOR_SUMMARY_URI"] = old


@contextmanager
def _summary_file(payload: dict[str, Any]) -> Iterator[str]:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=True) as fh:
        json.dump(payload, fh)
        fh.flush()
        yield fh.name


def _bad_matrix() -> dict[str, int]:
    return {"repetition:event_flood_pressure": 125}


def _load_from_summary(
    payload: dict[str, Any],
    *,
    profile: im_w.WorkloadProfile = im_w.FULL_PROFILE,
) -> dict[str, Any]:
    with _summary_file(payload) as uri:
        with _prior_summary_uri(uri):
            return im_w.load_generation_binding(cfg=_Cfg(), profile=profile)


def _assert(condition: bool, label: str, got: Any = None) -> None:
    if not condition:
        raise AssertionError(f"{label}: {got!r}")


def _check_profile_generation_passes(*, profile: im_w.WorkloadProfile) -> None:
    unique, duplicates = im_w.generate_cue_details(
        run_id="verify", stream_id="verify", profile=profile
    )
    binding = im_w._default_generation_binding(source="built_in", profile=profile)
    result = im_w._validate_generation(
        unique,
        duplicates,
        generation_binding=binding,
        profile=profile,
    )
    _assert(result["pass"], f"{profile.name} generation should pass", result)
    _assert(result["binding_pass"], f"{profile.name} binding should pass", result)


def check_default_generation_passes() -> None:
    _check_profile_generation_passes(profile=im_w.FULL_PROFILE)


def check_loop_probe_generation_passes() -> None:
    _check_profile_generation_passes(profile=im_w.LOOP_PROBE_PROFILE)


def check_forbidden_current_matrix_fails() -> None:
    profile = im_w.FULL_PROFILE
    unique, duplicates = im_w.generate_cue_details(
        run_id="verify", stream_id="verify", profile=profile
    )
    binding = im_w._default_generation_binding(source="built_in", profile=profile)
    current = im_w._validate_generation(
        unique,
        duplicates,
        generation_binding=binding,
        profile=profile,
    )
    binding["forbidden_adversarial_distributions"] = [
        current["adversarial_distribution"]
    ]
    result = im_w._validate_generation(
        unique,
        duplicates,
        generation_binding=binding,
        profile=profile,
    )
    _assert(not result["pass"], "forbidden current matrix should fail", result)
    _assert(result["forbidden_pattern_matched"], "forbidden pattern should match", result)


def check_prior_without_explicit_binding_adds_forbidden_pattern() -> None:
    bad_matrix = _bad_matrix()
    binding = _load_from_summary(
        {
            "run_id": "prior-no-explicit",
            "generation": {
                "pass": False,
                "adversarial_distribution": bad_matrix,
            },
        }
    )
    _assert(binding["source"] == "prior_summary", "source should be prior_summary", binding)
    _assert(
        binding["authority"] == "failure_direct_prior_run",
        "bad prior should escalate authority",
        binding,
    )
    _assert(
        binding["forbidden_adversarial_distributions"] == [bad_matrix],
        "bad prior matrix should become forbidden",
        binding,
    )


def check_explicit_prior_binding_cannot_launder_bad_generation() -> None:
    bad_matrix = _bad_matrix()
    prior_binding = im_w._default_generation_binding(
        source="built_in", profile=im_w.FULL_PROFILE
    )
    prior_binding["forbidden_adversarial_distributions"] = []
    binding = _load_from_summary(
        {
            "run_id": "prior-explicit",
            "generation_binding": prior_binding,
            "generation": {
                "pass": False,
                "adversarial_distribution": bad_matrix,
            },
        }
    )
    _assert(binding["source"] == "prior_summary", "source should be current load", binding)
    _assert(binding["source_uri"], "source_uri should point to prior summary", binding)
    _assert(binding["source_run_id"] == "prior-explicit", "source run should carry", binding)
    _assert(
        binding["authority"] == "failure_direct_prior_run",
        "explicit bad prior should escalate authority",
        binding,
    )
    _assert(
        binding["forbidden_adversarial_distributions"] == [bad_matrix],
        "explicit bad prior matrix should become forbidden",
        binding,
    )


def check_cross_profile_prior_does_not_create_false_forbidden_pattern() -> None:
    full_matrix = im_w._expected_adversarial_matrix(profile=im_w.FULL_PROFILE)
    binding = _load_from_summary(
        {
            "run_id": "prior-full",
            "workload_profile": {"name": "full"},
            "generation": {
                "pass": True,
                "adversarial_distribution": full_matrix,
            },
        },
        profile=im_w.LOOP_PROBE_PROFILE,
    )
    _assert(
        binding["profile"] == "loop_probe",
        "current binding should use loop_probe profile",
        binding,
    )
    _assert(
        binding["source_profile"] == "full",
        "source profile should be recorded",
        binding,
    )
    _assert(
        binding["forbidden_adversarial_distributions"] == [],
        "different profile should not become a forbidden pattern",
        binding,
    )


# --- second binding: dominant_axis_distribution_diversity_required -----------


def _load_dominant_axis_from_summary(
    payload: dict[str, Any],
    *,
    profile: im_w.WorkloadProfile = im_w.FULL_PROFILE,
) -> dict[str, Any]:
    with _summary_file(payload) as uri:
        with _prior_summary_uri(uri):
            return im_w.load_dominant_axis_binding(cfg=_Cfg(), profile=profile)


def _bad_dominant_axis_distribution() -> dict[str, int]:
    return {"provenance_chain": 50}


def check_default_dominant_axis_binding_passes() -> None:
    profile = im_w.FULL_PROFILE
    binding = im_w._default_dominant_axis_binding(source="built_in", profile=profile)
    result = im_w._validate_epistemic_surface(
        {"dominant_axis_distribution": {"claim": 10, "recall_process": 10, "provenance_chain": 10}},
        dominant_axis_binding=binding,
    )
    _assert(result["pass"], "default dominant axis binding should pass", result)
    _assert(result["binding_pass"], "default binding_pass should be true", result)
    _assert(
        binding["authority"] == "spec_default",
        "default binding authority should be spec_default",
        binding,
    )


def check_forbidden_current_dominant_axis_fails() -> None:
    profile = im_w.FULL_PROFILE
    bad = _bad_dominant_axis_distribution()
    binding = im_w._default_dominant_axis_binding(source="built_in", profile=profile)
    binding["forbidden_dominant_axis_distributions"] = [bad]
    result = im_w._validate_epistemic_surface(
        {"dominant_axis_distribution": dict(bad)},
        dominant_axis_binding=binding,
    )
    _assert(not result["pass"], "current dominant_axis matching forbidden should fail", result)
    _assert(result["forbidden_pattern_matched"], "forbidden_pattern_matched should be true", result)


def check_passing_prior_does_not_create_dominant_axis_forbidden_pattern() -> None:
    bad = _bad_dominant_axis_distribution()
    binding = _load_dominant_axis_from_summary(
        {
            "run_id": "prior-pass",
            "pass": True,
            "failure_stage": None,
            "workload_profile": {"name": "full"},
            "epistemic_surface": {"dominant_axis_distribution": bad},
        }
    )
    _assert(
        binding["forbidden_dominant_axis_distributions"] == [],
        "passing prior should not seed a forbidden pattern even if distribution exists",
        binding,
    )
    _assert(
        binding["authority"] == "execution_evidence_from_prior_run",
        "passing prior should not escalate authority",
        binding,
    )


def check_failed_prior_without_explicit_binding_seeds_forbidden_dominant_axis() -> None:
    bad = _bad_dominant_axis_distribution()
    binding = _load_dominant_axis_from_summary(
        {
            "run_id": "prior-failed-no-explicit",
            "pass": False,
            "failure_stage": "replay",
            "workload_profile": {"name": "full"},
            "epistemic_surface": {"dominant_axis_distribution": bad},
        }
    )
    _assert(binding["source"] == "prior_summary", "source should be prior_summary", binding)
    _assert(
        binding["authority"] == "failure_direct_prior_run",
        "failed prior should escalate authority",
        binding,
    )
    _assert(
        binding["forbidden_dominant_axis_distributions"] == [bad],
        "failed prior distribution should become forbidden",
        binding,
    )


def check_explicit_prior_dominant_axis_binding_cannot_launder_failed_run() -> None:
    bad = _bad_dominant_axis_distribution()
    prior_binding = im_w._default_dominant_axis_binding(
        source="built_in", profile=im_w.FULL_PROFILE
    )
    prior_binding["forbidden_dominant_axis_distributions"] = []
    binding = _load_dominant_axis_from_summary(
        {
            "run_id": "prior-failed-explicit",
            "pass": False,
            "failure_stage": "replay",
            "workload_profile": {"name": "full"},
            "epistemic_surface": {"dominant_axis_distribution": bad},
            "dominant_axis_binding": prior_binding,
        }
    )
    _assert(binding["source"] == "prior_summary", "source should be set to current load", binding)
    _assert(binding["source_uri"], "source_uri should point to prior summary", binding)
    _assert(
        binding["source_run_id"] == "prior-failed-explicit",
        "source_run_id should carry through",
        binding,
    )
    _assert(
        binding["authority"] == "failure_direct_prior_run",
        "explicit failed prior should still escalate authority",
        binding,
    )
    _assert(
        binding["forbidden_dominant_axis_distributions"] == [bad],
        "explicit failed prior distribution should still become forbidden",
        binding,
    )


def check_cross_profile_prior_does_not_create_false_dominant_axis_forbidden_pattern() -> None:
    bad = _bad_dominant_axis_distribution()
    binding = _load_dominant_axis_from_summary(
        {
            "run_id": "prior-full-failed",
            "pass": False,
            "failure_stage": "replay",
            "workload_profile": {"name": "full"},
            "epistemic_surface": {"dominant_axis_distribution": bad},
        },
        profile=im_w.LOOP_PROBE_PROFILE,
    )
    _assert(
        binding["profile"] == "loop_probe",
        "current binding should use loop_probe profile",
        binding,
    )
    _assert(
        binding["source_profile"] == "full",
        "source profile should be recorded",
        binding,
    )
    _assert(
        binding["forbidden_dominant_axis_distributions"] == [],
        "cross-profile failed prior must not seed a forbidden pattern",
        binding,
    )


def run() -> dict[str, Any]:
    checks = [
        check_default_generation_passes,
        check_loop_probe_generation_passes,
        check_forbidden_current_matrix_fails,
        check_prior_without_explicit_binding_adds_forbidden_pattern,
        check_explicit_prior_binding_cannot_launder_bad_generation,
        check_cross_profile_prior_does_not_create_false_forbidden_pattern,
        # second binding: dominant_axis_distribution_diversity_required
        check_default_dominant_axis_binding_passes,
        check_forbidden_current_dominant_axis_fails,
        check_passing_prior_does_not_create_dominant_axis_forbidden_pattern,
        check_failed_prior_without_explicit_binding_seeds_forbidden_dominant_axis,
        check_explicit_prior_dominant_axis_binding_cannot_launder_failed_run,
        check_cross_profile_prior_does_not_create_false_dominant_axis_forbidden_pattern,
    ]
    for check in checks:
        check()
    return {
        "pass": True,
        "checks": [check.__name__ for check in checks],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
