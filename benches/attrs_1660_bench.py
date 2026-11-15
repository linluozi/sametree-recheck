"""Benchmark the attrs ``asdict`` default path (PR python-attrs/attrs#1660)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from _harness import main  # noqa: E402

import attr  # noqa: E402


@attr.define
class Leaf:
    x: int
    y: str


@attr.define
class Tree:
    a: int
    b: str
    c: Leaf
    d: list


def _small():
    obj = Leaf(1, "x")
    return lambda: attr.asdict(obj)


def _nested():
    obj = Tree(1, "s", Leaf(2, "y"), [Leaf(i, str(i)) for i in range(8)])
    return lambda: attr.asdict(obj)


def _wide():
    cls = attr.make_class("W", {"f%d" % i: attr.ib() for i in range(24)})
    obj = cls(*range(24))
    return lambda: attr.asdict(obj)


def builders():
    return {"small_2field": _small, "nested_list8": _nested, "wide_24field": _wide}


if __name__ == "__main__":
    main(builders)
