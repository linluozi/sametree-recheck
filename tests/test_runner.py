import os
import sys
import textwrap

import pytest

from sametree_recheck.runner import _env_for, run_bench, run_tests
from sametree_recheck.trees import TreeError

PY = sys.executable


def test_env_for_resolves_relative_pythonpath_against_the_tree(tmp_path):
    env = _env_for(str(tmp_path), {"PYTHONPATH": "src"})
    assert env["PYTHONPATH"] == os.path.join(str(tmp_path), "src")
    assert "PYTHONPATH" not in _env_for(str(tmp_path), None)


def test_env_for_keeps_absolute_pythonpath_and_extra_vars(tmp_path):
    env = _env_for(str(tmp_path), {"PYTHONPATH": "/abs" + os.pathsep + "src", "FOO": "1"})
    assert env["PYTHONPATH"] == os.pathsep.join(
        ["/abs", os.path.join(str(tmp_path), "src")]
    )
    assert env["FOO"] == "1"


def _write_bench(tmp_path, body):
    script = tmp_path / "bench.py"
    script.write_text(textwrap.dedent(body), encoding="utf-8")
    return str(script)


def test_run_bench_accepts_well_formed_payload(tmp_path):
    script = _write_bench(
        tmp_path,
        """
        import json, sys
        reps = int(sys.argv[sys.argv.index("--reps") + 1])
        json.dump({"scenarios": {"s": [1.0] * reps}, "iters": {"s": 3}}, sys.stdout)
        """,
    )
    payload = run_bench(PY, str(tmp_path), script, 1, 4, 30)
    assert payload["scenarios"]["s"] == [1.0] * 4


def test_run_bench_rejects_wrong_sample_count(tmp_path):
    script = _write_bench(
        tmp_path,
        'import json, sys\njson.dump({"scenarios": {"s": [1.0]}}, sys.stdout)\n',
    )
    with pytest.raises(TreeError):
        run_bench(PY, str(tmp_path), script, 1, 4, 30)


def test_run_bench_rejects_a_non_zero_exit(tmp_path):
    script = _write_bench(tmp_path, "import sys\nsys.exit(3)\n")
    with pytest.raises(TreeError):
        run_bench(PY, str(tmp_path), script, 1, 2, 30)


def test_run_tests_substitutes_python_and_reports_failure(tmp_path):
    ok = run_tests(
        PY,
        str(tmp_path),
        {"command": ["{python}", "-c", "print('x')"], "env": {"PYTHONPATH": "."}},
        30,
    )
    assert ok["passed"] is True
    assert ok["returncode"] == 0
    bad = run_tests(PY, str(tmp_path), {"command": ["{python}", "-c", "raise SystemExit(2)"]}, 30)
    assert bad["passed"] is False
    assert bad["returncode"] == 2
