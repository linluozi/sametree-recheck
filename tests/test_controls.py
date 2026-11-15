import pytest

from sametree_recheck.stats import split_controls


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
