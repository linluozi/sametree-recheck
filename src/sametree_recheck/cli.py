"""Command line interface: ``run`` and ``certificate``."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile

from . import __version__
from .runner import run_bench, run_tests
from .stats import control_bias, decide, speedup, split_controls, summarize
from .trees import (
    TreeError,
    canonical_sha256,
    evidence,
    make_patched,
    materialize,
)

REQUIRED_KEYS = (
    "id",
    "repo",
    "repo_url",
    "base_commit",
    "patch_file",
    "bench",
    "tests",
    "retain_median_gte",
    "worst_case_gte",
)


def load_case(path):
    with open(path, encoding="utf-8") as fh:
        case = json.load(fh)
    missing = [key for key in REQUIRED_KEYS if key not in case]
    if missing:
        raise SystemExit("case %s is missing keys: %s" % (path, ", ".join(missing)))
    return case


def resolve(case_path, rel):
    if os.path.isabs(rel):
        return rel
    root = os.path.dirname(os.path.dirname(os.path.abspath(case_path)))
    return os.path.normpath(os.path.join(root, rel))


def build_trees(case, case_path, tmpdir):
    pristine = os.path.join(tmpdir, "pristine")
    patched = os.path.join(tmpdir, "patched")
    patch_file = resolve(case_path, case["patch_file"])
    materialize(case["repo_url"], case["base_commit"], pristine)
    make_patched(pristine, patch_file, patched)
    ev = evidence(
        case["repo"], case["repo_url"], case["base_commit"], patch_file, pristine, patched
    )
    return pristine, patched, ev


def _write_raw(path, tree_label, scenarios):
    with open(path, "w", encoding="utf-8") as fh:
        for name in sorted(scenarios):
            for rep, seconds in enumerate(scenarios[name]):
                fh.write(
                    json.dumps(
                        {
                            "tree": tree_label,
                            "scenario": name,
                            "rep": rep,
                            "seconds_per_op": seconds,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )


def cmd_run(args):
    case_path = os.path.abspath(args.case)
    case = load_case(case_path)
    python = args.python or sys.executable
    bench_spec = case["bench"]
    test_spec = case["tests"]
    warmup = int(bench_spec.get("warmup", 3))
    reps = int(bench_spec.get("reps", 7))
    os.makedirs(args.out_dir, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="sametree-", dir=args.tmp) as tmpdir:
        pristine, patched, ev = build_trees(case, case_path, tmpdir)
        if not ev["heads_equal"] or not ev["pristine_status_clean"]:
            raise SystemExit("same-tree guard failed: %s" % json.dumps(ev, sort_keys=True))
        if ev["changed_file_count"] < 1:
            raise SystemExit("patch changed no touched file; refusing to benchmark")

        base_tests = run_tests(python, pristine, test_spec, test_spec.get("timeout", 300))
        patched_tests = run_tests(python, patched, test_spec, test_spec.get("timeout", 300))

        script = resolve(case_path, bench_spec["script"])
        env_extra = bench_spec.get("env")
        base_bench = run_bench(
            python, pristine, script, warmup, reps, bench_spec.get("timeout", 300), env_extra
        )
        patched_bench = run_bench(
            python, patched, script, warmup, reps, bench_spec.get("timeout", 300), env_extra
        )

        names = sorted(set(base_bench["scenarios"]) & set(patched_bench["scenarios"]))
        controls = list(bench_spec.get("control_scenarios", []))
        scenarios = {}
        for name in names:
            scenarios[name] = {
                "baseline": summarize(base_bench["scenarios"][name]),
                "patched": summarize(patched_bench["scenarios"][name]),
                "speedup": speedup(base_bench["scenarios"][name], patched_bench["scenarios"][name]),
                "control": name in controls,
            }
        speedups = {name: scenarios[name]["speedup"] for name in names}
        decision_speedups, control_speedups = split_controls(speedups, controls)
        bias = control_bias(control_speedups)
        bias_limit = float(case.get("control_bias_limit", 0.10))
        decision = decide(
            decision_speedups,
            base_tests,
            patched_tests,
            float(case["retain_median_gte"]),
            float(case["worst_case_gte"]),
        )
        if bias > bias_limit and decision["verdict"] != "INCONCLUSIVE":
            decision["verdict"] = "INCONCLUSIVE"
            decision["reasons"].append(
                "control scenario deviates %.1f%% from 1.0x (> %.0f%% limit): "
                "per-process timing bias, effect not resolvable"
                % (bias * 100.0, bias_limit * 100.0)
            )

    replay_certificate = canonical_sha256(
        {
            "evidence_sha256": canonical_sha256(ev),
            "case_id": case["id"],
            "patch_sha256": ev["patch_sha256"],
            "tests": {
                "pristine": {k: base_tests[k] for k in ("command", "passed", "returncode")},
                "patched": {k: patched_tests[k] for k in ("command", "passed", "returncode")},
            },
            "thresholds": {
                "retain_median_gte": float(case["retain_median_gte"]),
                "worst_case_gte": float(case["worst_case_gte"]),
            },
        }
    )

    report = {
        "schema": "sametree-report/1",
        "tool_version": __version__,
        "case_id": case["id"],
        "upstream": case["repo"],
        "pr": case.get("pr"),
        "claim": case.get("claim"),
        "thresholds": {
            "retain_median_gte": float(case["retain_median_gte"]),
            "worst_case_gte": float(case["worst_case_gte"]),
        },
        "evidence": ev,
        "evidence_sha256": canonical_sha256(ev),
        "replay_certificate": replay_certificate,
        "tests": {"pristine": base_tests, "patched": patched_tests},
        "bench": {
            "warmup": warmup,
            "reps": reps,
            "script": os.path.relpath(resolve(case_path, bench_spec["script"]), os.path.dirname(case_path)),
            "control_scenarios": controls,
            "control_speedups": control_speedups,
            "control_bias": bias,
            "control_bias_limit": bias_limit,
            "iters": {"pristine": base_bench.get("iters"), "patched": patched_bench.get("iters")},
            "python": base_bench.get("meta", {}).get("python"),
            "executable": base_bench.get("meta", {}).get("executable"),
            "scenarios": scenarios,
        },
        "verdict": decision["verdict"],
        "median_speedup": decision["median_speedup"],
        "worst_case_speedup": decision["worst_case_speedup"],
        "verdict_reasons": decision["reasons"],
    }

    report_path = os.path.join(args.out_dir, "%s.json" % case["id"])
    raw_path = os.path.join(args.out_dir, "%s.raw.jsonl" % case["id"])
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
        fh.write("\n")
    _write_raw(raw_path, "pristine", base_bench["scenarios"])
    with open(raw_path, "a", encoding="utf-8") as fh:
        for name in sorted(patched_bench["scenarios"]):
            for rep, seconds in enumerate(patched_bench["scenarios"][name]):
                fh.write(
                    json.dumps(
                        {
                            "tree": "patched",
                            "scenario": name,
                            "rep": rep,
                            "seconds_per_op": seconds,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )

    print("report: %s" % report_path)
    print("raw:    %s" % raw_path)
    print("verdict: %s  median=%.4fx worst=%.4fx" % (
        report["verdict"],
        report["median_speedup"] or 0.0,
        report["worst_case_speedup"] or 0.0,
    ))
    for reason in report["verdict_reasons"]:
        print("  - %s" % reason)
    return 0


def cmd_certificate(args):
    case_path = os.path.abspath(args.case)
    case = load_case(case_path)
    with tempfile.TemporaryDirectory(prefix="sametree-", dir=args.tmp) as tmpdir:
        _pristine, _patched, ev = build_trees(case, case_path, tmpdir)
    print(json.dumps(ev, indent=2, sort_keys=True))
    print("evidence_sha256: %s" % canonical_sha256(ev))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="sametree-recheck", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="materialise both trees and recheck the PR claim")
    run.add_argument("--case", required=True)
    run.add_argument("--out-dir", default="reports")
    run.add_argument("--python", default=None, help="interpreter used for bench + tests")
    run.add_argument("--tmp", default=None, help="parent dir for the two temporary trees")
    run.set_defaults(func=cmd_run)

    cert = sub.add_parser("certificate", help="re-materialise the trees and print evidence only")
    cert.add_argument("--case", required=True)
    cert.add_argument("--tmp", default=None)
    cert.set_defaults(func=cmd_certificate)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except TreeError as exc:
        print("tree error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
