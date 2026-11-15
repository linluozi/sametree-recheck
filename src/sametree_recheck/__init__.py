"""sametree-recheck: same-tree evidence recheck for performance PRs.

A performance PR may legitimately be measured against the *same* commit it
proposes to change.  It may also, often by accident, be measured across two
different trees (for example a released wheel against a git checkout).  This
package forces the first kind of comparison and refuses the second: the
pristine and the patched tree are both materialised at one base commit, the
base commit is asserted on both, and the touched files are hashed on both
sides before any timing is recorded.
"""

__version__ = "1.0.0"
__all__ = ["__version__"]
