#!/usr/bin/env bash
# Explicit recovery when a published native seed cannot read current sources.
# This builds stage zero only: bootstrap_native.sh must still certify the pair.
set -euo pipefail
if [[ $# != 1 ]]; then
    echo 'Usage: PYTHON=python3 bootstrap_hosted_seed.sh NEW_OUTPUT_DIRECTORY' >&2
    exit 2
fi
seed_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
seed_output=$(realpath -m -- "$1")
seed_python=$(command -v -- "${PYTHON:-python3}")
for seed_directory in dewy udewy library tools; do
    if [[ $seed_output == "$seed_root/$seed_directory" || $seed_output == "$seed_root/$seed_directory/"* ]]; then
        echo 'The output must be outside the source directories being copied.' >&2
        exit 2
    fi
done
# A fresh snapshot avoids target-dependent cache reuse and records exactly
# which sources the hosted compiler consumed, including local edits.
mkdir -- "$seed_output"
mkdir -- "$seed_output/source"
cp -a -- "$seed_root/dewy" "$seed_root/udewy" "$seed_root/library" \
    "$seed_root/tools" "$seed_root/VERSION" "$seed_output/source/"
cd -- "$seed_output/source"
export DEWY_LIBRARY_ROOT="$PWD/library"
find dewy udewy library tools -type f \( -name '*.py' -o -name '*.dewy' -o -name '*.udewy' -o -name '*.bin' -o -name '*.sh' \) -print0 |
    sort -z | xargs -0 sha256sum -- > "$seed_output/SOURCE_SHA256SUMS"
sha256sum VERSION >> "$seed_output/SOURCE_SHA256SUMS"
"$seed_python" --version > "$seed_output/PYTHON_VERSION"
"$seed_python" -m udewy --target x86_64 --no-debug-info -c udewy/bootstrap/main.udewy
cp -- __dewycache__/udewy/bootstrap/main "$seed_output/udewy"
"$seed_python" -m dewy --target x86_64 --timings --compile dewy/bootstrap/main.dewy
cp -- __dewycache__/dewy/bootstrap/main "$seed_output/dewy"
"$seed_output/dewy" --version
"$seed_output/udewy" --help > /dev/null
(cd -- "$seed_output"; sha256sum dewy udewy > SHA256SUMS)
echo "Hosted stage-zero pair: $seed_output (native fixed-point verification still required)"
