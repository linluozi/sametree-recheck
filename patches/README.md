# Patch provenance

These diffs are inputs to the rechecker.  They are unmodified GitHub pull-request
diffs retrieved through the GitHub API and are included so a reader can reproduce
every report in `reports/` byte-for-byte.

| file | upstream | licence | source |
| --- | --- | --- | --- |
| `attrs-1660.diff` | [python-attrs/attrs](https://github.com/python-attrs/attrs) | MIT | PR #1660, base `2a1fb86d44816afcc60e86d57956ce3604820326` |
| `croniter-298.diff` | [kiorky/croniter](https://github.com/kiorky/croniter) | MIT | PR #298, base `ddb3495cf4eb1e7b0cc33b6baa0e9c4f36fb0c60` |
| `jsonpatch-274.diff` | [stefankoegl/python-json-patch](https://github.com/stefankoegl/python-json-patch) | BSD-3-Clause | PR #274, base `cc1229ae0892bdad91b2b81403ebbf2529eec6db` |

The patches are applied to a pristine checkout of the *same* base commit; the
reports in `reports/*.json` record the sha256 of the pristine and the patched
copy of every touched file, so a divergent upstream tree cannot pass silently.

No upstream source code is vendored; only the diffs above are stored.
