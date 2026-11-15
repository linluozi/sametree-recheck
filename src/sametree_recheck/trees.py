"""Materialise two trees at one base commit and certify they match."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess


class TreeError(RuntimeError):
    pass


def run(cmd, cwd=None, env=None, timeout=300, check=True):
    proc = subprocess.run(
        cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout
    )
    if check and proc.returncode != 0:
        raise TreeError(
            "command failed (%d): %s\n%s"
            % (proc.returncode, " ".join(cmd), (proc.stderr or "")[-2000:])
        )
    return proc


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head(tree):
    return run(["git", "-C", tree, "rev-parse", "HEAD"]).stdout.strip()


def status_clean(tree):
    return run(["git", "-C", tree, "status", "--porcelain"]).stdout.strip() == ""


def materialize(repo_url, base_commit, dest):
    """Fetch exactly ``base_commit`` and assert HEAD equals it."""
    os.makedirs(dest, exist_ok=True)
    run(["git", "init", "-q", dest])
    run(["git", "-C", dest, "remote", "add", "origin", repo_url])
    run(
        ["git", "-C", dest, "fetch", "-q", "--depth=1", "origin", base_commit],
        timeout=180,
    )
    run(["git", "-C", dest, "checkout", "-q", "FETCH_HEAD"])
    head = git_head(dest)
    if head != base_commit:
        raise TreeError("base commit mismatch: asked %s got %s" % (base_commit, head))
    return head


_TOUCHED_RE = re.compile(r"^\+\+\+ b/(.+)$", re.M)


def touched_files(patch_text):
    return sorted({p.strip() for p in _TOUCHED_RE.findall(patch_text)})


def make_patched(pristine, patch_file, dest):
    """Copy the pristine tree byte-for-byte, then apply the patch to the copy."""
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.copytree(pristine, dest, symlinks=True)
    patch_abs = os.path.abspath(patch_file)
    run(["git", "-C", dest, "apply", "--check", patch_abs])
    run(["git", "-C", dest, "apply", patch_abs])
    if git_head(dest) != git_head(pristine):
        raise TreeError("patch changed HEAD; it is not a same-tree patch")
    return touched_files(open(patch_file, encoding="utf-8").read())


def file_sha256(path):
    return sha256_file(path) if os.path.exists(path) else None


def evidence(repo, repo_url, base_commit, patch_file, pristine, patched):
    """Deterministic, timing-free facts that make the comparison auditable."""
    patch_text = open(patch_file, encoding="utf-8").read()
    files = {}
    for rel in touched_files(patch_text):
        before = file_sha256(os.path.join(pristine, rel))
        after = file_sha256(os.path.join(patched, rel))
        files[rel] = {
            "pristine_sha256": before,
            "patched_sha256": after,
            "changed": before != after,
        }
    return {
        "schema": "sametree-evidence/1",
        "repo": repo,
        "repo_url": repo_url,
        "base_commit": base_commit,
        "pristine_head": git_head(pristine),
        "patched_head": git_head(patched),
        "heads_equal": git_head(pristine) == git_head(patched),
        "pristine_status_clean": status_clean(pristine),
        "patch_sha256": sha256_file(patch_file),
        "touched_files": files,
        "changed_file_count": sum(1 for v in files.values() if v["changed"]),
    }


def canonical_sha256(obj):
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()
