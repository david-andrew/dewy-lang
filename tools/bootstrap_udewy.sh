#!/usr/bin/env bash
# Rebuild µDewy twice using a native seed, then verify a fixed point.
# No Python is used here. A seed may come from a release, or be built once with
# `python -m udewy -c udewy/bootstrap/main.udewy` during development.
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
    echo "Usage: $0 NATIVE_UDEWY_SEED [OUTPUT_DIRECTORY]" >&2
    exit 2
fi

bootstrap_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
bootstrap_seed=$(realpath -- "$1")
bootstrap_output=$(realpath -m -- "${2:-$bootstrap_root/__dewycache__/native-bootstrap}")
if [[ ! -x "$bootstrap_seed" ]]; then
    echo "Native µDewy seed is not executable: $bootstrap_seed" >&2
    exit 2
fi
mkdir -p -- "$bootstrap_output"

# Retain each compiler before compiling the next one: the standard compiler
# cache path is reused, but no running compiler is overwritten.
cp -- "$bootstrap_seed" "$bootstrap_output/udewy-stage0"
cd -- "$bootstrap_root"
for bootstrap_generation in 1 2; do
    bootstrap_previous=$((bootstrap_generation - 1))
    "$bootstrap_output/udewy-stage$bootstrap_previous" -c udewy/bootstrap/main.udewy
    cp -- __dewycache__/udewy/bootstrap/main "$bootstrap_output/udewy-stage$bootstrap_generation"
    "$bootstrap_output/udewy-stage$bootstrap_generation" --help > /dev/null
done

cmp -- "$bootstrap_output/udewy-stage1" "$bootstrap_output/udewy-stage2"
cp -- "$bootstrap_output/udewy-stage2" "$bootstrap_output/udewy"
(
    cd -- "$bootstrap_output"
    sha256sum udewy-stage0 udewy-stage1 udewy-stage2 udewy > SHA256SUMS
)
echo "Verified identical native µDewy generations: $bootstrap_output/udewy"
