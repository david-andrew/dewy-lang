"""Scratch-output handling for the dated audit probes."""

import argparse
from pathlib import Path


def output_directory():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="scratch directory for generated sources and observations",
    )
    args = parser.parse_args()
    destination = args.output_dir.resolve()
    bundle = Path(__file__).resolve().parent.parent
    if destination == bundle or bundle in destination.parents:
        parser.error("choose a scratch directory outside the recorded audit bundle")
    destination.mkdir(parents=True, exist_ok=True)
    return destination
