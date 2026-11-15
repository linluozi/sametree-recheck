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
trees differ in far more than the patch, so the ratio can be arbitrarily wrong.
This round measured a claimed `1.98x` at **1.14x** on one tree (and at 1.89x on
one nested shape only).  `sametree-recheck` makes the tree mismatch impossible to
hide: both worktrees must report the identical `git rev-parse HEAD`, the pristine
tree must be clean, and the report stores the sha256 of the pristine and patched
copy of each touched file.  A benchmark that silently used two different trees
cannot produce a passing certificate.

## 本轮创新

**B 档（新意）：把「已开 PR 的 baseline 与 patched 是否同树」做成可执行的独立复核器。**
台账里已有 `hunk-ablation`（逐 hunk 归因）、`perfclaim-guard`（运行时拒绝假声明）、
`caseproof`（用例数内容寻址），但没有任何一个把「同树」本身当成可判定的前置条件，也没有
「同树加速比不达标即撤回」的可执行判据。本仓库第一次把 `heads_equal` + 每个被改文件的
pristine/patched 双 sha256 写进证书，并用它对本账号三个已开 PR 出「保留/撤回」三值裁决。
和已有条目的区别：`perfclaim-guard` 检查一条性能*声明*的四个可伪造点；这里检查一次*测量*
的两棵树是否同源——前者管声明，后者管测量。**新增的一层**：每个 case 可声明一个 control
场景（不改动代码的路径，真实加速比恒为 1.00x），工具用它的偏离量当作仪器偏置；当 control
偏离超过 `control_bias_limit` 时拒绝出裁决——这是「测量本身是否可信」的可执行判据，
本轮正是靠它发现 json-patch 的 ~5% 效应低于仪器偏置（未加 control 时会得出 0.60x 这类假数字）。

## This round's verdicts

Thresholds were fixed in `cases/*.json` before running: retain needs a median
same-tree speedup **≥ 1.30x**, and the decision envelope needs **≥ 1.00x** on
every scenario that exercises the changed code.

| PR | claimed | same-tree median | reported worst case | verdict |
| --- | --- | --- | --- | --- |
| [python-attrs/attrs#1660](https://github.com/python-attrs/attrs/pull/1660) | 1.98x | **1.1442x** | 1.1362x | **RETRACT** |
| [kiorky/croniter#298](https://github.com/kiorky/croniter/pull/298) | — | **2.3003x** | 1.7388x | **RETAIN** |
| [stefankoegl/python-json-patch#274](https://github.com/stefankoegl/python-json-patch/pull/274) | 1.33x | 0.5966x ‡ | 0.5948x ‡ | **RETRACT** |

† The json-patch row is **not a trustworthy magnitude**: across seven independent
runs of the same case the decision median ranged **0.60x–1.07x**, and the control
scenario (the unaffected `json.loads` path, whose true speedup is exactly 1.00x)
ranged **0.90x–1.45x**.  That is per-process timing bias of the same order as the
effect under test, so the instrument cannot resolve json-patch's ~5 % effect.  The
committed report (median 0.5966x) is one sample; no run of seven reached even
1.10x, so the conclusion "nothing near the 1.30x bar" is robust, but the number is
not.  The tool now measures the control and refuses to issue a verdict when the
control deviates by more than `control_bias_limit` (`control_bias()` in
`src/sametree_recheck/stats.py`, tested); the committed report predates that gate
being set to 5 % for this case.

### attrs #1660 — the headline 1.98x is a nested-only result

| scenario | baseline median | patched median | speedup |
| --- | --- | --- | --- |
| `nested_list8` (attrs nested in a list) | 10.995 µs | 5.636 µs | **1.9508x** |
| `small_2field` | 0.783 µs | 0.684 µs | 1.1442x |
| `wide_24field` | 4.285 µs | 3.771 µs | 1.1362x |

The fast path really does win ~1.95x when `asdict` walks a nested attrs tree, but
on the flat and wide shapes that dominate ordinary use it is ~1.14x.  The median
across the three default-path shapes is 1.1442x, below the pre-registered 1.30x
retain bar.  Upstream tests: `53 passed` in **both** trees.

### croniter #298 — retained

| scenario | baseline median | patched median | speedup |
| --- | --- | --- | --- |
| `next_5min_datetime` | 40.827 µs | 17.501 µs | 2.3328x |
| `prev_5min_datetime` | 39.555 µs | 17.076 µs | 2.3165x |
| `next_5min_float` | 39.737 µs | 17.397 µs | 2.2841x |
| `next_15sec_datetime` | 19.646 µs | 11.299 µs | **1.7388x** |

Median 2.3003x, worst 1.7388x, both clear the bar, and this case reproduces
tightly across runs.  Upstream tests: `179 passed, 870 subtests passed` in both
trees.

### json-patch #274 — retracted

| scenario | baseline median | patched median | speedup |
| --- | --- | --- | --- |
| `from_diff_graph` | 398.585 µs | 529.522 µs | 0.5966x |
| `make_patch_graph` | 397.979 µs | 529.687 µs | 0.5948x |
| `from_diff_primitive` | 110.301 µs | 124.006 µs | 0.7776x |
| `patch_serialize` (control, true 1.00x) | 4.638 µs | 3.196 µs | 1.4513x |

In this run the control came out at **1.45x** — a 45 % deviation on a path the
patch cannot touch — which is the clearest possible signal that the two
subprocesses were not measured under comparable conditions.  A later run under
the 5 % control gate measured the same control at 0.98x but still put
`from_diff_graph` at 0.60x.  Seven runs of this case gave decision medians
0.60x–1.07x.  **Conclusion: this case's timing is not resolvable at this scale,
and the tool's control gate exists to say so.**  The defensible statement is
narrow: no run came close to 1.30x.  Upstream tests: `346 passed, 448 subtests
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
| G4 | every scenario ≥ 1.00x | `verdict` in each report | attrs 1.1362x pass; croniter 1.7388x pass; json-patch 0.5948x fail (but see the json-patch stability note above) |
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
- Relative standard deviation was ≤ 6.6 % on every attrs and croniter scenario
  that entered a verdict; json-patch's `from_diff_primitive` baseline reached
  12.1 % and its `patch_serialize` control swung 45 % between runs — that case is
  explicitly discussed as unresolvable above.  The medians, not the means, drive
  the ratios.
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
