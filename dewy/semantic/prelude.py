"""Ordered source files implicitly available to Dewy modules."""

from pathlib import Path

project_root = Path(__file__).parents[2]

PRELUDE_FILES = (
    project_root / 'library' / 'path.dewy',
)
