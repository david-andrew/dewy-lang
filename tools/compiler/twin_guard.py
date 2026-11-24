"""Guard a landing's live inputs, leaf coverage and compatibility with the pinned seed.

The landing script invokes this module by its historical name.
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


BEHAVIOR = re.compile(r"\b(?:assert\s|(?:compare(?:_\w+)?|leaf_compilers|same_output)\s*\()")
BUILD_INPUTS = ("compiler", "lib", "bootstrap-seed", "tools/core.py", "tools/compiler/build.py",
                "tools/compiler/seed_archive.py", "LICENSE")


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True)


def names_leaf(path: str, source: str, stem: str) -> bool:
    return (stem in Path(path).stem or stem in source) and bool(BEHAVIOR.search(source))


def check_range(repo: Path, base: str, head: str) -> list[str]:
    """Read both revisions from Git so this works for historical ranges too."""
    paths = set(git(repo, "ls-tree", "-r", "--name-only", head, "compiler", "bootstrap").splitlines())
    leaves = {path for path in paths if path.endswith(".dewy")}
    retired = ({str(Path(leaf).with_suffix(".jo")) for leaf in leaves} | {"compiler/dewy_reader_seed.jo"}) & paths
    retired.update(path for path in paths if path.startswith("bootstrap/") and path.endswith(".jo"))
    errors = [f"{path}: historical bootstrap source in the live tree" for path in sorted(retired)]
    changed = leaves.intersection(git(repo, "diff", "--name-only", base, head, "--", "compiler").splitlines())
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

    errors.extend(f"{leaf}: no named behavior test" for leaf in sorted(changed) if not has_test(Path(leaf).stem))
    return errors


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
    if git(repo, "diff", "--name-only", args.base, args.head, "--", *BUILD_INPUTS):
        # The landing runs on the target checkout. Bind the compatibility result
        # to that revision, including newly added or untracked compiler inputs.
        if (git(repo, "rev-parse", args.head) != git(repo, "rev-parse", "HEAD")
                or git(repo, "status", "--porcelain", "--", *BUILD_INPUTS)):
            parser.error("seed compatibility requires a clean checkout of the landing head")
        from tools.core import toolchain
        toolchain(bootstrap=True)
    print(f"seed compatibility guard: {args.base}..{args.head} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
