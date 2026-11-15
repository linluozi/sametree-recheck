# sametree-recheck — refuse cross-tree performance claims

`sametree-recheck` takes a pull request's diff, materialises **the same base
commit twice** (pristine and patched), asserts both trees are at that commit,
hashes every touched file on both sides, then runs the *same* benchmark and the
*same* upstream test command in each tree.  It emits a `RETAIN` / `RETRACT` /
`INCONCLUSIVE` verdict against thresholds you declare **before** measuring.

It changes nothing upstream.  It exists because a headline speedup is only
believable if the two numbers came from the same tree.

Upstream: none

## Why cross-tree comparisons happen

A very common accident: the "before" number is taken from an installed release
(a wheel, a `pip install`) and the "after" number from a git checkout.  The two
trees differ in far more than the patch, so the ratio can be arbitrarily wrong —
this round found a claimed `1.98x` that is `1.14x` on one tree.  `sametree-recheck`
makes that failure impossible to hide: both worktrees must report the identical
`git rev-parse HEAD`, the pristine tree must be clean, and the report stores the
sha256 of the pristine and patched copy of each touched file.  A benchmark that
silently used two different trees cannot produce a passing certificate.

## 本轮创新

**B 档（新意）：把「已开 PR 的 baseline 与 patched 是否同树」做成可执行的独立复核器。**
台账里已有 `hunk-ablation`（逐 hunk 归因）、`perfclaim-guard`（运行时拒绝假声明）、
`caseproof`（用例数内容寻址），但没有任何一个把「同树」本身当成可判定的前置条件，也没有
「同树加速比不达标即撤回」的可执行判据。本仓库第一次把 `heads_equal` + 每个被改文件的
pristine/patched 双 sha256 写进证书，并用它对本账号三个已开 PR 出「保留/撤回」三值裁决。
和已有条目的区别：`perfclaim-guard` 检查一条性能*声明*的四个可伪造点；这里检查一次*测量*
的两棵树是否同源——前者管声明，后者管测量。

## This round's verdicts

Thresholds were fixed in `cases/*.json` before running: retain needs a median
same-tree speedup **≥ 1.30x**, and the decision envelope needs **≥ 1.00x** on
every scenario that exercises the changed code.

| PR | claimed | same-tree median | reported worst case | verdict |
| --- | --- | --- | --- | --- |
| [python-attrs/attrs#1660](https://github.com/python-attrs/attrs/pull/1660) | 1.98x | **1.1386x** | 1.1264x | **RETRACT** |
| [kiorky/croniter#298](https://github.com/kiorky/croniter/pull/298) | — | **2.2768x** | 1.7158x | **RETAIN** |
| [stefankoegl/python-json-patch#274](https://github.com/stefankoegl/python-json-patch/pull/274) | 1.33x | **1.0437x** | 0.9927x † | **RETRACT** |

† `jsonpatch-274` reports one **control** scenario (`patch_serialize`) at 0.9927x.  The
patch cannot affect that path — it only serialises an already-built patch — so it is
pure noise on untouched code.  The committed report is *conservative*: it was produced
before control support existed, so it counts the control in both the median (1.0437x)
and the envelope (0.9927x).  The three decision-path scenarios are
1.0348x / 1.0526x / 1.0655x, i.e. even excluding the control the median is 1.0526x,
still far below the 1.30x bar.  The verdict is RETRACT under either convention.
The tool now supports excluding controls via `bench.control_scenarios`
(`split_controls` in `src/sametree_recheck/stats.py`, covered by `tests/test_controls.py`);
the report was deliberately not re-run, so the stricter number stands.

### attrs #1660 — the headline 1.98x is a nested-only result

| scenario | baseline median | patched median | speedup |
| --- | --- | --- | --- |
| `nested_list8` (attrs nested in a list) | 10.732 µs | 5.674 µs | **1.8915x** |
| `small_2field` | 0.790 µs | 0.694 µs | 1.1386x |
| `wide_24field` | 4.180 µs | 3.711 µs | 1.1264x |

The fast path really does win ~1.89x when `asdict` walks a nested attrs tree, but
on the flat and wide shapes that dominate ordinary use it is ~1.13x.  The median
across the three default-path shapes is 1.1386x, below the pre-registered 1.30x
retain bar.  Upstream tests: `53 passed` in **both** trees.

### croniter #298 — retained

| scenario | baseline median | patched median | speedup |
| --- | --- | --- | --- |
| `next_5min_float` | 40.504 µs | 17.576 µs | 2.3044x |
| `next_5min_datetime` | 40.502 µs | 17.681 µs | 2.2907x |
| `prev_5min_datetime` | 39.053 µs | 17.259 µs | 2.2628x |
| `next_15sec_datetime` | 19.755 µs | 11.514 µs | **1.7158x** |

Median 2.2768x, worst 1.7158x, both clear the bar.  Upstream tests:
`179 passed, 870 subtests passed` in both trees.

### json-patch #274 — retracted

| scenario | baseline median | patched median | speedup |
| --- | --- | --- | --- |
| `from_diff_graph` | 401.204 µs | 387.698 µs | 1.0348x |
| `make_patch_graph` | 402.901 µs | 382.776 µs | 1.0526x |
| `from_diff_primitive` | 107.501 µs | 100.889 µs | 1.0655x |
| `patch_serialize` (control) | 3.214 µs | 3.238 µs | 0.9927x |

Median 1.0437x, far below 1.30x.  Upstream tests: `346 passed, 448 subtests
passed` in both trees.

## How to reproduce

```bash
# 1. install the tool + the interpreters its cases need
python3 -m venv /tmp/stv && /tmp/stv/bin/pip install -q pytest python-dateutil hypothesis pytz jsonpointer

# 2. recheck any case (clones, patches, benchmarks and tests both trees)
PYTHONPATH=src /tmp/stv/bin/python -m sametree_recheck run \
  --case cases/attrs-1660.json --out-dir reports --python /tmp/stv/bin/python

# 3. reproduce all three reports at once
PYTHON=/tmp/stv/bin/python bash scripts/run_all.sh

# the tool's own tests
PYTHONPATH=src /tmp/stv/bin/python -m pytest tests -q
```

Re-running step 2 re-materialises the trees and rewrites
`reports/attrs-1660.json` plus `reports/attrs-1660.raw.jsonl`.  Because the
rechecker clones and patched-forms the trees from scratch every run, and because
both worktrees must report the same base commit, the tree-level evidence is
deterministic.  Check it with:

```bash
PYTHONPATH=src /tmp/stv/bin/python -m sametree_recheck certificate \
  --case cases/attrs-1660.json | tail -1     # evidence_sha256, must equal the report's
```

## Gates

| gate | what it checks | reproduce | result |
| --- | --- | --- | --- |
| G1 | upstream test suite green in pristine **and** patched tree | `tests.command` in each `cases/*.json` | 3/3 green in both trees |
| G2 | same-tree certificate: `heads_equal`, pristine clean, per-touched-file dual sha256 | `certificate` subcommand / `evidence` in each report | 3/3 pass, 1 changed file each |
| G3 | median same-tree speedup ≥ 1.30x | `verdict` in each report | croniter pass; attrs 1.1386x, json-patch 1.0437x fail |
| G4 | every scenario ≥ 1.00x | `verdict` in each report | attrs 1.1264x pass; croniter 1.7158x pass; json-patch reported worst 0.9927x fail (control-only; decision-path min 1.0348x) |
| — | peak RSS | **not measured this round** — this product's gate is the same-tree certificate, not the `-opt-lab` RSS gate | n/a |

No number in this README was predicted; every one is read back from
`reports/*.json`, which are the tool's own committed output.

## Environment

- CPU: AMD EPYC 7K62 48-Core Processor (4 vCPU exposed), memory 3.6 GiB
- Runtime: CPython **3.12.3**, `pytest 9.2.0`
- Bench protocol: 3 warmup rounds discarded, then **7 timed rounds**; each round
  is auto-calibrated to ~0.20 s of work and reports seconds **per operation**.
  Every raw per-round sample is committed under `reports/*.raw.jsonl`.
- Determinism: `croniter` cases use a fixed base datetime; `attrs` cases build
  fixed objects; the `jsonpatch` graph case uses `random.Random(1042)`.
- Relative standard deviation was ≤ 5.9 % on every scenario that entered a
  verdict (the worst is `prev_5min_datetime`'s baseline at 5.9 %); the medians,
  not the means, drive the ratios.
- Only one interpreter (3.12.3) exists on this machine, so no cross-version
  matrix was produced.

## Layout

```
src/sametree_recheck/   trees.py (materialise + certify), runner.py, stats.py, cli.py
benches/                one benchmark per case, shared auto-calibrating harness
cases/                  thresholds, base commit, test command, claim
patches/                the PR diffs under test (provenance in patches/README.md)
reports/                committed tool output: verdicts + raw per-round samples
tests/                  the tool's own tests (no network needed)
```
