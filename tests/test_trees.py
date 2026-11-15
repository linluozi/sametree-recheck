import json
import os
import subprocess

import pytest

from sametree_recheck.trees import (
    TreeError,
    canonical_sha256,
    evidence,
    git_head,
    make_patched,
    materialize,
    sha256_file,
    status_clean,
    touched_files,
)

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
}


def _init_repo(path, files):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    for name, text in files.items():
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    env = dict(os.environ)
    env.update(GIT_ENV)
    subprocess.run(
        ["git", "-C", str(path), "commit", "-qm", "init"], check=True, env=env
    )
    return path


def test_touched_files_parses_plus_headers():
    text = (
        "diff --git a/x.py b/x.py\n"
        "--- a/x.py\n"
        "+++ b/x.py\n"
        "@@ -1 +1 @@\n"
        "-a\n"
        "+b\n"
        "--- a/pkg/y.py\n"
        "+++ b/pkg/y.py\n"
    )
    assert touched_files(text) == ["pkg/y.py", "x.py"]
    assert touched_files(text) == touched_files(text)


def test_canonical_sha256_is_key_order_independent():
    assert canonical_sha256({"a": 1, "b": [2, 3]}) == canonical_sha256(
        {"b": [2, 3], "a": 1}
    )
    assert canonical_sha256({"a": 1}) != canonical_sha256({"a": 2})


def test_canonical_sha256_is_json_stable():
    payload = {"x": [1, 2, {"y": None}], "z": "é"}
    assert canonical_sha256(payload) == canonical_sha256(
        json.loads(json.dumps(payload))
    )


def test_make_patched_applies_patch_without_moving_head(tmp_path):
    repo = _init_repo(tmp_path / "up", {"a.txt": "one\n", "keep.txt": "k\n"})
    patch = tmp_path / "p.diff"
    patch.write_text(
        "--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-one\n+two\n", encoding="utf-8"
    )
    dest = tmp_path / "patched"
    files = make_patched(str(repo), str(patch), str(dest))
    assert files == ["a.txt"]
    assert (dest / "a.txt").read_text(encoding="utf-8") == "two\n"
    assert (dest / "keep.txt").read_text(encoding="utf-8") == "k\n"
    assert git_head(dest) == git_head(str(repo))


def test_make_patched_rejects_a_patch_that_does_not_apply(tmp_path):
    repo = _init_repo(tmp_path / "up", {"a.txt": "one\n"})
    patch = tmp_path / "bad.diff"
    patch.write_text(
        "--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-nope\n+two\n", encoding="utf-8"
    )
    with pytest.raises(TreeError):
        make_patched(str(repo), str(patch), str(tmp_path / "patched"))


def test_evidence_records_before_after_hashes_and_same_head(tmp_path):
    repo = _init_repo(tmp_path / "up", {"src/m.py": "x = 1\n"})
    patch = tmp_path / "p.diff"
    patch.write_text(
        "--- a/src/m.py\n+++ b/src/m.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n",
        encoding="utf-8",
    )
    dest = tmp_path / "patched"
    make_patched(str(repo), str(patch), str(dest))
    ev = evidence("o/r", "url", git_head(str(repo)), str(patch), str(repo), str(dest))
    assert ev["heads_equal"] is True
    assert ev["pristine_status_clean"] is True
    assert ev["changed_file_count"] == 1
    assert ev["touched_files"]["src/m.py"]["changed"] is True
    assert ev["touched_files"]["src/m.py"]["pristine_sha256"] == sha256_file(
        str(repo / "src" / "m.py")
    )
    assert ev["patch_sha256"] == sha256_file(str(patch))


def test_materialize_rejects_head_mismatch(tmp_path):
    repo = _init_repo(tmp_path / "up", {"a.txt": "one\n"})
    with pytest.raises(TreeError):
        materialize(str(repo), "0" * 40, str(tmp_path / "clone"))


def test_status_clean_true_on_fresh_repo(tmp_path):
    repo = _init_repo(tmp_path / "up", {"a.txt": "one\n"})
    assert status_clean(str(repo)) is True
    (repo / "a.txt").write_text("changed\n", encoding="utf-8")
    assert status_clean(str(repo)) is False
