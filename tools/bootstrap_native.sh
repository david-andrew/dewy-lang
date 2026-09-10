#!/usr/bin/env bash
# Rebuild the Dewy/µDewy compiler pair without Python and verify a fixed point.
# The seeds must already be native executables. The first Dewy seed may have
# been compiled by the hosted compiler; no hosted compiler is invoked here.
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
    echo "Usage: $0 NATIVE_DEWY_SEED NATIVE_UDEWY_SEED [OUTPUT_DIRECTORY]" >&2
    exit 2
fi

bootstrap_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
bootstrap_dewy=$(realpath -- "$1")
bootstrap_udewy=$(realpath -- "$2")
bootstrap_output=$(realpath -m -- "${3:-$bootstrap_root/__dewycache__/native-pair}")
for bootstrap_seed in "$bootstrap_dewy" "$bootstrap_udewy"; do
    if [[ ! -x "$bootstrap_seed" ]]; then
        echo "Native compiler seed is not executable: $bootstrap_seed" >&2
        exit 2
    fi
done
mkdir -p -- "$bootstrap_output"
cp -- "$bootstrap_dewy" "$bootstrap_output/dewy-stage0"
cp -- "$bootstrap_udewy" "$bootstrap_output/udewy-stage0"
cd -- "$bootstrap_root"

# Refuse to certify generations compiled while their inputs were changing.
# This also binds release packaging to the source/library tree actually used.
find dewy/bootstrap udewy/bootstrap udewy/stdlib library \
    -type f \( -name '*.dewy' -o -name '*.udewy' -o -name '*.bin' \) -print0 |
    sort -z | xargs -0 sha256sum > "$bootstrap_output/SOURCE_SHA256SUMS"
sha256sum VERSION tools/dewy_test.dewy >> "$bootstrap_output/SOURCE_SHA256SUMS"

# Preserve a generation before rebuilding the shared cache artifact. Each
# Dewy compiler runs with the new µDewy generation and the source library
# belonging to this checkout, independent of the user's installed compilers.
for bootstrap_generation in 1 2; do
    bootstrap_previous=$((bootstrap_generation - 1))
    echo "Building native compiler generation $bootstrap_generation"
    bootstrap_started=$SECONDS
    "$bootstrap_output/udewy-stage$bootstrap_previous" -c udewy/bootstrap/main.udewy
    cp -- __dewycache__/udewy/bootstrap/main "$bootstrap_output/udewy-stage$bootstrap_generation"
    DEWY_LIBRARY_ROOT="$bootstrap_root/library" \
        DEWY_UDEWY="$bootstrap_output/udewy-stage$bootstrap_generation" \
        "$bootstrap_output/dewy-stage$bootstrap_previous" -c dewy/bootstrap/main.dewy
    cp -- __dewycache__/dewy/bootstrap/main "$bootstrap_output/dewy-stage$bootstrap_generation"
    "$bootstrap_output/udewy-stage$bootstrap_generation" --help > /dev/null
    "$bootstrap_output/dewy-stage$bootstrap_generation" --version
    echo "Generation $bootstrap_generation completed in $((SECONDS - bootstrap_started)) seconds"
    sha256sum --check --status "$bootstrap_output/SOURCE_SHA256SUMS"
done

cmp -- "$bootstrap_output/udewy-stage1" "$bootstrap_output/udewy-stage2"
cmp -- "$bootstrap_output/dewy-stage1" "$bootstrap_output/dewy-stage2"
cp -- "$bootstrap_output/udewy-stage2" "$bootstrap_output/udewy"
cp -- "$bootstrap_output/dewy-stage2" "$bootstrap_output/dewy"
(
    cd -- "$bootstrap_output"
    sha256sum dewy-stage0 dewy-stage1 dewy-stage2 dewy \
        udewy-stage0 udewy-stage1 udewy-stage2 udewy > SHA256SUMS
)
echo "Verified identical native compiler generations: $bootstrap_output"
