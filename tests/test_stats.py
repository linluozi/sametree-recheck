import math

import pytest

from sametree_recheck.stats import _quantile, decide, speedup, summarize


def test_quantiles_match_linear_interpolation():
    s = sorted([1.0, 2.0, 3.0, 4.0])
    assert _quantile(s, 0.25) == pytest.approx(1.75)
    assert _quantile(s, 0.5) == pytest.approx(2.5)
    assert _quantile(s, 0.75) == pytest.approx(3.25)


def test_summarize_reports_median_p25_p75():
    out = summarize([1.0, 2.0, 3.0, 4.0, 5.0])
    assert out["n"] == 5
    assert out["median_seconds"] == 3.0
    assert out["p25_seconds"] == 2.0
    assert out["p75_seconds"] == 4.0
    assert out["min_seconds"] == 1.0
    assert out["max_seconds"] == 5.0


def test_summarize_rejects_non_positive_and_bool():
    with pytest.raises(ValueError):
        summarize([])
    with pytest.raises(ValueError):
        summarize([0.0])
    with pytest.raises(ValueError):
        summarize([-1.0])
    with pytest.raises(ValueError):
        summarize([True])


def test_relative_stdev_is_zero_for_constant_samples():
    out = summarize([2.0, 2.0, 2.0])
    assert out["relative_stdev"] == 0.0


def test_speedup_uses_medians_not_means():
    # one outlier must not move the median-based ratio
    baseline = [1.0, 1.0, 1.0, 1000.0]
    patched = [0.5, 0.5, 0.5, 0.5]
    assert speedup(baseline, patched) == pytest.approx(2.0)


def _tests(passed=True):
    return {"passed": passed, "returncode": 0 if passed else 1, "summary": "x"}


def test_decide_retains_when_both_thresholds_clear():
    out = decide(
        {"a": 2.0, "b": 1.5, "c": 1.4}, _tests(), _tests(), 1.30, 1.00
    )
    assert out["verdict"] == "RETAIN"
    assert out["median_speedup"] == pytest.approx(1.5)


def test_decide_retracts_when_median_below_threshold():
    out = decide({"a": 1.9, "b": 1.1, "c": 1.0}, _tests(), _tests(), 1.30, 1.00)
    assert out["verdict"] == "RETRACT"
    assert "median same-tree speedup" in out["reasons"][0]


def test_decide_retracts_when_worst_case_below_floor():
    out = decide({"a": 5.0, "b": 5.0, "c": 0.97}, _tests(), _tests(), 1.30, 1.00)
    assert out["verdict"] == "RETRACT"
    assert "worst-case" in out["reasons"][0]


def test_decide_is_inconclusive_when_patched_tests_fail():
    out = decide({"a": 5.0, "b": 5.0}, _tests(), _tests(passed=False), 1.30, 1.00)
    assert out["verdict"] == "INCONCLUSIVE"


def test_decide_is_inconclusive_without_scenarios():
    out = decide({}, _tests(), _tests(), 1.30, 1.00)
    assert out["verdict"] == "INCONCLUSIVE"
    assert out["median_speedup"] is None


def test_decide_handles_even_count_median():
    out = decide({"a": 1.0, "b": 3.0}, _tests(), _tests(), 1.30, 1.00)
    assert out["median_speedup"] == pytest.approx(2.0)
    assert out["worst_case_speedup"] == pytest.approx(1.0)
    assert out["verdict"] == "RETAIN"


def test_decide_median_boundary_is_inclusive():
    out = decide({"a": 1.30, "b": 1.30}, _tests(), _tests(), 1.30, 1.00)
    assert out["verdict"] == "RETAIN"


def test_nan_is_rejected():
    with pytest.raises(ValueError):
        summarize([float("nan")])
