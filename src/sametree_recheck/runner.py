"""Run the same benchmark and the same test command in both trees."""

from __future__ import annotations

import json
import os
import subprocess

from .trees import TreeError


def _env_for(tree, extra):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    if not extra:
        return env
    parts = []
    for key, value in extra.items():
        if key == "PYTHONPATH":
            for piece in value.split(os.pathsep):
                if not piece:
                    continue
                parts.append(
                    piece if os.path.isabs(piece) else os.path.normpath(os.path.join(tree, piece))
                )
        else:
            env[key] = value
    if parts:
        env["PYTHONPATH"] = os.pathsep.join(parts)
    return env


def run_bench(python, tree, script, warmup, reps, timeout, env_extra=None):
    cmd = [python, os.path.abspath(script), "--warmup", str(warmup), "--reps", str(reps)]
    proc = subprocess.run(
        cmd,
        cwd=tree,
        env=_env_for(tree, env_extra),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise TreeError(
            "bench failed in %s (%d)\n%s" % (tree, proc.returncode, (proc.stderr or "")[-2000:])
        )
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if not lines:
        raise TreeError("bench printed nothing in %s" % tree)
    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise TreeError("bench did not print a JSON line in %s: %s" % (tree, exc)) from exc
    scenarios = payload.get("scenarios") or {}
    if not scenarios:
        raise TreeError("bench returned no scenarios in %s" % tree)
    for name, samples in scenarios.items():
        if len(samples) != reps:
            raise TreeError(
                "scenario %s returned %d samples, expected %d"
                % (name, len(samples), reps)
            )
    return payload


def run_tests(python, tree, spec, timeout):
    argv = [python if arg == "{python}" else arg for arg in spec["command"]]
    proc = subprocess.run(
        argv,
        cwd=os.path.join(tree, spec.get("cwd", ".")),
        env=_env_for(tree, spec.get("env")),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    tail = [line for line in (proc.stdout or "").strip().splitlines() if line.strip()]
    if tail:
        summary = tail[-1]
    else:
        err = [line for line in (proc.stderr or "").strip().splitlines() if line.strip()]
        summary = err[-1] if err else ""
    return {
        "command": " ".join(argv),
        "passed": proc.returncode == 0,
        "returncode": proc.returncode,
        "summary": summary[-300:],
    }
