"""Check changed compiler leaves against their frozen twins and differential tests.

Usage: python3 -m tools.compiler.twin_guard BASE HEAD
The range is the complete landing batch, not each intermediate commit. This lets
one commit repair a twin changed by another commit in the same batch.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from collections.abc import Callable
from pathlib import Path


# These twins intentionally do not implement their Dewy leaves in bootstrap
# generations without the Dewy frontend. Add a name only with its reason.
BOOTSTRAP_STUBS = {
    "call_forward": "The bootstrap frontend has no Dewy call-forwarding forms; its twin returns -1 for both probes.",
}

DIFFERENTIAL_CALL = re.compile(r"\b(?:compare(?:_\w+)?|leaf_compilers|same_output)\s*\(")


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True)


def names_leaf(path: str, source: str, stem: str) -> bool:
    return (stem in Path(path).stem or stem in source) and bool(DIFFERENTIAL_CALL.search(source))


def changed_leaf_errors(changed: set[str], has_test: Callable[[str], bool]) -> list[str]:
    """Check paths in one landing range; has_test(stem) searches the target tree."""
    errors = []
    for leaf in sorted(path for path in changed if re.fullmatch(r"compiler/[^/]+\.dewy", path)):
        stem = Path(leaf).stem
        if stem in BOOTSTRAP_STUBS:
            continue
        twin = str(Path(leaf).with_suffix(".jo"))
        # (dewy_reader.jo only forwards to its implementation, dewy_reader_seed.jo)
        seed = str(Path(leaf).with_name(f"{stem}_seed.jo"))
        if twin not in changed and seed not in changed:
            errors.append(f"{leaf}: frozen twin {twin} did not change")
        if not has_test(stem):
            errors.append(f"{leaf}: no named differential test in tests/test_*.py")
    return errors


def check_range(repo: Path, base: str, head: str) -> list[str]:
    """Read both revisions from Git so this works for historical ranges too."""
    changed = set(git(repo, "diff", "--name-only", base, head, "--", "compiler").splitlines())
    test_paths = [path for path in git(repo, "ls-tree", "-r", "--name-only", head, "tests").splitlines()
                  if Path(path).name.startswith("test_") and path.endswith(".py")]
    available = set(test_paths)
    sources: dict[str, str] = {}

    def source(path: str) -> str:
        if path not in sources:
            sources[path] = git(repo, "show", f"{head}:{path}")
        return sources[path]

    def has_test(stem: str) -> bool:
        # Most leaves have a test with the stem in its filename. Search test
        # contents only for suites named after a larger subsystem.
        for path in test_paths:
            if stem in Path(path).stem and names_leaf(path, source(path), stem):
                return True
        if not test_paths:
            return False
        matches = subprocess.run(["git", "-C", str(repo), "grep", "-l", "-F", stem,
                                  head, "--", "tests"], text=True, capture_output=True)
        if matches.returncode not in (0, 1):
            raise subprocess.CalledProcessError(matches.returncode, matches.args, matches.stdout, matches.stderr)
        for line in matches.stdout.splitlines():
            path = line.split(":", 1)[1]
            if path in available and names_leaf(path, source(path), stem):
                return True
        return False

    return changed_leaf_errors(changed, has_test)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", help="landing base revision")
    parser.add_argument("head", help="landing head revision")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    errors = check_range(repo, args.base, args.head)
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"twin guard: {args.base}..{args.head} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
