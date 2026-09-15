#!/usr/bin/env bash
# Optimize an existing C-generated Dewy seed using native compilation workloads.
# No Python compiler participates. Keep the original seed and its fixed-point
# evidence; this produces a separately identified optimization variant.
set -euo pipefail
if [[ $# -lt 3 ]]; then
    echo 'Usage: DEWY_UDEWY=/path/to/native/udewy profile_dewy_seed.sh GENERATED_C OUTPUT_DIRECTORY TRAINING_SOURCE...' >&2
    exit 2
fi
profile_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
profile_source=$(realpath -- "$1")
profile_output=$(realpath -m -- "$2")
shift 2
profile_cc=${DEWY_PGO_CC:-gcc}
profile_jobs=${DEWY_BOOTSTRAP_LTO_JOBS:-8}
profile_no_pre=${DEWY_BOOTSTRAP_GCC_NO_PRE:-1}
if [[ ! -f $profile_source || -e $profile_output || ! $profile_jobs =~ ^[1-9][0-9]*$ ||
      ! $profile_no_pre =~ ^[01]$ ]]; then
    echo 'Need an existing C source, a new output directory, positive LTO jobs, and GCC_NO_PRE=0 or 1.' >&2
    exit 2
fi
if [[ -z ${DEWY_UDEWY:-} || ! -x $DEWY_UDEWY ]]; then
    echo 'Set DEWY_UDEWY to the native micro-Dewy executable used for training.' >&2
    exit 2
fi
export DEWY_UDEWY
DEWY_UDEWY=$(realpath -- "$DEWY_UDEWY")
export DEWY_LIBRARY_ROOT=${DEWY_LIBRARY_ROOT:-"$profile_root/library"}
DEWY_LIBRARY_ROOT=$(realpath -- "$DEWY_LIBRARY_ROOT")
profile_training=()
for source in "$@"; do
    profile_training+=("$(realpath -e -- "$source")")
done
profile_cc=$(command -v -- "$profile_cc")
mkdir -p -- "$profile_output/profiles"
profile_flags=(-std=c99 -O2 "-flto=$profile_jobs")
if [[ $profile_no_pre == 1 ]]; then
    profile_flags+=(-fno-tree-pre -fno-code-hoisting)
fi
# Preserve source/object naming between instrumentation and profile use: GCC
# keys its counters by translation unit. Never silently accept missing data.
profile_command=("$profile_cc" "${profile_flags[@]}" -o "$profile_output/compiler" "$profile_source")
{
    "$profile_cc" --version
    printf '\nBase command: '; printf '%q ' "${profile_command[@]}"; printf '\n'
    sha256sum -- "$profile_source" "$DEWY_UDEWY" "${profile_training[@]}"
    printf 'Library: %s\n' "$DEWY_LIBRARY_ROOT"
} > "$profile_output/inputs.txt"
find "$DEWY_LIBRARY_ROOT" -type f \( -name '*.dewy' -o -name '*.udewy' -o -name '*.bin' \) -print0 |
    sort -z | xargs -0 sha256sum -- > "$profile_output/library.sha256"

echo 'Building instrumented Dewy seed'
{ time "${profile_command[@]}" "-fprofile-generate=$profile_output/profiles"; } > "$profile_output/instrument.log" 2>&1
profile_index=0
for source in "${profile_training[@]}"; do
    profile_work="$profile_output/training-$profile_index"
    mkdir -- "$profile_work"
    echo "Training on $source"
    (
        cd -- "$profile_work"
        time "$profile_output/compiler" --timings --target x86_64 --compile "$source"
    ) > "$profile_output/training-$profile_index.log" 2>&1
    profile_index=$((profile_index + 1))
done
if ! find "$profile_output/profiles" -type f -name '*.gcda' -print -quit | grep -q .; then
    echo 'Training produced no GCC profile counters; preserving the instrumented build for inspection.' >&2
    exit 1
fi
cp -- "$profile_output/compiler" "$profile_output/compiler.instrumented"
find "$profile_output/profiles" -type f -name '*.gcda' -print0 |
    sort -z | xargs -0 sha256sum -- > "$profile_output/profiles.sha256"
echo 'Building profile-guided Dewy seed'
{ time "${profile_command[@]}" "-fprofile-use=$profile_output/profiles" -Werror=coverage-mismatch -Werror=missing-profile; } > "$profile_output/optimize.log" 2>&1
sha256sum -- "$profile_output/compiler" > "$profile_output/compiler.sha256"
echo "Profile-guided seed: $profile_output/compiler"
