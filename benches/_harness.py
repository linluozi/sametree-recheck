"""Auto-calibrating per-op bench harness shared by the case benchmarks.

Each bench script calls :func:`main` with a mapping ``name -> builder`` where a
builder returns a zero-argument callable performing one unit of work.  The
harness calibrates the iteration count to roughly ``target_seconds`` per round,
runs ``--warmup`` discarded rounds, then records ``--reps`` per-op samples.

It prints one JSON object on the last stdout line::

    {"scenarios": {name: [seconds_per_op, ...]}, "iters": {name: k}, "meta": {...}}
"""

from __future__ import annotations

import argparse
import json
import sys
import time


def main(builders, target_seconds=0.20, max_iters=500000):
    parser = argparse.ArgumentParser()
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--reps", type=int, default=7)
    args = parser.parse_args()

    out = {
        "scenarios": {},
        "iters": {},
        "meta": {
            "python": sys.version.split()[0],
            "executable": sys.executable,
            "target_seconds": target_seconds,
        },
    }
    for name, build in builders().items():
        fn = build()
        start = time.perf_counter()
        fn()
        estimate = max(time.perf_counter() - start, 1e-7)
        k = min(max_iters, max(1, int(target_seconds / estimate)))
        for _ in range(args.warmup):
            for _ in range(k):
                fn()
        samples = []
        for _ in range(args.reps):
            start = time.perf_counter()
            for _ in range(k):
                fn()
            samples.append((time.perf_counter() - start) / k)
        out["scenarios"][name] = samples
        out["iters"][name] = k
    json.dump(out, sys.stdout)
    sys.stdout.write("\n")
