import pytest

from sametree_recheck.stats import control_bias, split_controls


def test_split_controls_keeps_controls_out_of_the_decision_set():
    speedups = {"hot_path": 2.5, "second_path": 1.8, "untouched_control": 0.97}
    decision, control = split_controls(speedups, ["untouched_control"])
    assert decision == {"hot_path": 2.5, "second_path": 1.8}
    assert control == {"untouched_control": 0.97}


def test_split_controls_without_controls_is_a_no_op():
    speedups = {"a": 1.1, "b": 1.2}
    decision, control = split_controls(speedups, None)
    assert decision == speedups
    assert control == {}


def test_split_controls_ignores_unknown_control_names():
    decision, control = split_controls({"a": 1.0}, ["missing"])
    assert decision == {"a": 1.0}
    assert control == {}


def test_control_bias_is_zero_without_controls():
    assert control_bias({}) == 0.0


def test_control_bias_is_the_largest_deviation_from_one():
    assert control_bias({"c": 1.04}) == pytest.approx(0.04)
    assert control_bias({"c": 1.45, "d": 0.93}) == pytest.approx(0.45)

