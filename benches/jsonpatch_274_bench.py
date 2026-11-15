"""Benchmark json-patch ``from_diff`` (PR stefankoegl/python-json-patch#274)."""

import copy
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())

from _harness import main  # noqa: E402

import jsonpatch  # noqa: E402


def _graph_docs():
    rnd = random.Random(1042)
    src = {
        "id": 1,
        "tags": [{"k": i, "w": rnd.random()} for i in range(20)],
        "meta": {"a": 1, "b": [1, 2, 3]},
    }
    dst = copy.deepcopy(src)
    dst["tags"][3]["k"] = 999
    dst["meta"]["c"] = 7
    del dst["meta"]["b"]
    dst["tags"].insert(0, dst["tags"].pop(10))
    return src, dst


def _from_diff_graph():
    src, dst = _graph_docs()
    return lambda: jsonpatch.JsonPatch.from_diff(src, dst)


def _make_patch_graph():
    src, dst = _graph_docs()
    return lambda: jsonpatch.make_patch(src, dst)


def _from_diff_primitive():
    src = {"a": [1, 2, 3], "b": True, "c": "x"}
    dst = {"a": [1, 3, 2], "b": False, "c": "y"}
    return lambda: jsonpatch.JsonPatch.from_diff(src, dst)


def _from_diff_roundtrip():
    src, dst = _graph_docs()
    patch = jsonpatch.JsonPatch.from_diff(src, dst)
    text = json.dumps(patch.patch)
    return lambda: json.loads(text)


def builders():
    return {
        "from_diff_graph": _from_diff_graph,
        "make_patch_graph": _make_patch_graph,
        "from_diff_primitive": _from_diff_primitive,
        "patch_serialize": _from_diff_roundtrip,
    }


if __name__ == "__main__":
    main(builders)
