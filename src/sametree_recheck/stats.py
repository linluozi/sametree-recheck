"""Pure statistics and the retain/retract decision rule."""

from __future__ import annotations

import math
import statistics

VERDICTS = ("RETAIN", "RETRACT", "INCONCLUSIVE")


def _quantile(sorted_values, q):
    """Linear-interpolation quantile (same convention as numpy default)."""
    n = len(sorted_values)
    if n == 0:
        raise ValueError("no samples")
    if n == 1:
        return float(sorted_values[0])
    pos = q * (n - 1)
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return float(sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac)


def summarize(samples):
    """Return median/p25/p75/min/max/mean/rsd for positive per-op seconds."""
    if not samples:
        raise ValueError("no samples")
    for s in samples:
        if (
            isinstance(s, bool)
            or not isinstance(s, (int, float))
            or not math.isfinite(s)
            or s <= 0
        ):
            raise ValueError("samples must be finite, strictly positive numbers")
    s = sorted(float(x) for x in samples)
    med = statistics.median(s)
    mean = statistics.fmean(s)
    sd = statistics.stdev(s) if len(s) > 1 else 0.0
    return {
        "n": len(s),
        "median_seconds": med,
        "p25_seconds": _quantile(s, 0.25),
        "p75_seconds": _quantile(s, 0.75),
        "min_seconds": s[0],
        "max_seconds": s[-1],
        "mean_seconds": mean,
        "relative_stdev": (sd / mean) if mean else 0.0,
    }


def speedup(baseline_samples, patched_samples):
    """Baseline median / patched median. >1 means the patch is faster."""
    base = summarize(baseline_samples)["median_seconds"]
    opt = summarize(patched_samples)["median_seconds"]
    if opt <= 0:
        raise ValueError("patched median must be positive")
    return base / opt


def split_controls(speedups, control_names):
    """Return (decision_speedups, control_speedups).

    A control scenario does not exercise the changed code (for example, a
    serialisation path the patch cannot affect).  It is still reported so the
    reader can see it, but it must not sway the retain/retract verdict.
    """
    controls = set(control_names or [])
    decision = {k: v for k, v in speedups.items() if k not in controls}
    observed = {k: v for k, v in speedups.items() if k in controls}
    return decision, observed


def decide(scenario_speedups, base_tests, patched_tests, retain_median_gte, worst_case_gte):
    """Apply the documented rule and return a structured decision.

    RETAIN   median >= retain_median_gte AND every scenario >= worst_case_gte
             AND upstream tests pass in both trees.
    RETRACT  tests pass but at least one threshold is missed.
    INCONCLUSIVE  a tree could not be exercised (tests failing / no scenarios).
    """
    reasons = []
    if not scenario_speedups:
        return {
            "verdict": "INCONCLUSIVE",
            "median_speedup": None,
            "worst_case_speedup": None,
            "reasons": ["no benchmark scenario produced samples"],
        }
    if not base_tests.get("passed"):
        reasons.append("upstream tests fail on the pristine base tree")
    if not patched_tests.get("passed"):
        reasons.append("upstream tests fail on the patched tree")
    values = list(scenario_speedups.values())
    median_speedup = statistics.median(values)
    worst = min(values)
    if reasons:
        return {
            "verdict": "INCONCLUSIVE",
            "median_speedup": median_speedup,
            "worst_case_speedup": worst,
            "reasons": reasons,
        }
    if median_speedup < retain_median_gte:
        reasons.append(
            "median same-tree speedup %.4fx < retain threshold %.2fx"
            % (median_speedup, retain_median_gte)
        )
    if worst < worst_case_gte:
        reasons.append(
            "worst-case same-tree speedup %.4fx < floor %.2fx" % (worst, worst_case_gte)
        )
    if reasons:
        return {
            "verdict": "RETRACT",
            "median_speedup": median_speedup,
            "worst_case_speedup": worst,
            "reasons": reasons,
        }
    return {
        "verdict": "RETAIN",
        "median_speedup": median_speedup,
        "worst_case_speedup": worst,
        "reasons": [
            "median %.4fx >= %.2fx and worst %.4fx >= %.2fx"
            % (median_speedup, retain_median_gte, worst, worst_case_gte)
        ],
    }
