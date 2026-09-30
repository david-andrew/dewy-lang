#!/usr/bin/env bash
# Validation tiers (dewy/ROADMAP.md, "Immediate work order", step 2).
#
#   certify.sh local [PYTEST_ARGS...]
#       The per-batch gate: the non-slow pytest suite on 8 workers. Hosted-built
#       test drivers are shared by content identity (tests/python_misc/
#       driver_artifacts.py), so unchanged compiler sources are not rebuilt.
#
#   certify.sh integration OUTPUT_DIRECTORY [COMMIT]
#       A frozen integration checkpoint for one commit (default HEAD): an
#       independent hosted-built seed, a three-generation native fixed point,
#       native execution checks, the complete paired hosted/native manifest and
#       the full pytest suite with independently built drivers, all for the same
#       source snapshot. Every step records its log and status in OUTPUT; the
#       summary names the commit it certifies. Steps continue after a failure so
#       one run reports everything; the exit status is nonzero if any failed.
#
# Scheduled/release certification is .github/workflows/release-native.yml,
# which requires a successful full test run for the exact published revision.
set -uo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
python=${PYTHON:-$root/.venv/bin/python}
[[ -x $python ]] || python=$(command -v python3)

usage() {
    sed -n '2,20p' "${BASH_SOURCE[0]}" >&2
    exit 2
}

case ${1:-} in
local)
    shift
    cd -- "$root"
    exec "$python" -m pytest tests -q -p no:cacheprovider -n 8 --dist loadfile -m 'not slow' \
        -o faulthandler_timeout=900 "$@"
    ;;
integration)
    [[ $# -ge 2 ]] || usage
    output=$(realpath -m -- "$2")
    commit=$(git -C "$root" rev-parse --verify "${3:-HEAD}^{commit}") || exit 2
    if [[ -e $output ]]; then
        echo "$output already exists; certification needs a fresh directory." >&2
        exit 2
    fi
    mkdir -p -- "$output"
    source="$output/source"
    git -C "$root" worktree add --detach "$source" "$commit" > /dev/null || exit 2
    summary="$output/SUMMARY"
    echo "commit $commit" > "$summary"
    failed=0
    step() {
        local name=$1
        shift
        local started=$SECONDS
        echo "== $name" >&2
        (cd -- "$source" && "$@") > "$output/$name.log" 2>&1
        local status=$?
        echo "$name status=$status seconds=$((SECONDS - started))" >> "$summary"
        [[ $status == 0 ]] || failed=1
        return $status
    }
    export DEWY_LIBRARY_ROOT="$source/library"
    ulimit -v 24000000
    step hosted-seed env PYTHON="$python" tools/bootstrap_hosted_seed.sh "$output/hosted-seed"
    step fixed-point tools/bootstrap_native.sh --target x86_64 --generations 3 \
        "$output/hosted-seed/dewy" "$output/hosted-seed/udewy" "$output/native"
    step check-native tools/check_native.sh "$output/native"
    step paired-manifest "$python" tools/check_compiler_parity.py --native-executable "$output/native/dewy" \
        --udewy-executable "$output/native/udewy" --cases tests/fixtures/phase1_parity_cases.json \
        --output "$output/parity" --shared-prelude-cache
    step full-pytest env DEWY_TEST_DRIVER_CACHE=0 "$python" -m pytest tests -q -p no:cacheprovider -n 8 \
        --dist loadfile -o faulthandler_timeout=900 --basetemp "$output/pytest-tmp"
    git -C "$root" worktree remove --force "$source" > /dev/null 2>&1 || true
    echo "certified=$((1 - failed))" >> "$summary"
    cat "$summary"
    exit $failed
    ;;
*)
    usage
    ;;
esac
