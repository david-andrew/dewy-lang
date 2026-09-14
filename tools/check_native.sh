#!/usr/bin/env bash
# Exercise an already-built native pair without invoking the hosted compiler.
# Fixed-point comparison alone cannot detect a consistently miscompiled pair.
set -euo pipefail
if [[ $# -lt 1 || $# -gt 2 || (${2:-1} != 1 && ${2:-1} != 2) ]]; then
    echo "Usage: $0 NATIVE_PAIR_DIRECTORY [1|2]" >&2
    exit 2
fi
check_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
check_pair=$(realpath -- "$1")
check_suffix=${2:+-stage$2}
check_dewy="$check_pair/dewy$check_suffix"
check_udewy="$check_pair/udewy$check_suffix"
check_work=$(mktemp -d "${TMPDIR:-/tmp}/dewy-native-check.XXXXXX")
trap 'rm -rf -- "$check_work"' EXIT
export DEWY_LIBRARY_ROOT="$check_root/library"
export DEWY_UDEWY="$check_udewy"
cd -- "$check_root"

cat > "$check_work/scalar.dewy" <<'EOF'
$no_prelude
let count=(value:int64):>int64=>if value =? 0 0 else count(value-1)+1
let combine=(left:int64 scale:int64=2 right:int64):>int64=>left+right*scale
let main=():>int64=>{
    let sum:int64=0
    loop i in 0..6 {sum+=i}
    if count(sum) not=? 21 {return 1}
    return combine(right=16 10)
}
EOF

# Exercise discovery and the per-file runner together. The nonzero result
# is intentional: one failed expectation must reach the directory's exit
# status, while parameterized cases each contribute a passing result.
mkdir -p "$check_work/tests/.hidden" "$check_work/tests/__dewycache__" "$check_work/tests/node_modules"
cat > "$check_work/tests/passing.dewy" <<'EOF'
$test(cases=(1 2 3))
let positive=(n:int64)=>{$expect n>?0}
let main=():>int64=>99
EOF
cat > "$check_work/tests/failing.dewy" <<'EOF'
$test
let fails=()=>{$expect false}
EOF
for ignored in .hidden __dewycache__ node_modules; do
    cp "$check_work/tests/failing.dewy" "$check_work/tests/$ignored/ignored.dewy"
done

expect_exit() {
    local expected=$1
    shift
    local actual=0
    timeout 180s "$@" || actual=$?
    if [[ $actual != "$expected" ]]; then
        echo "Expected exit $expected, got $actual: $*" >&2
        exit 1
    fi
}

for check_target in x86_64 c; do
    echo "Checking native pair with $check_target output"
    # Ordinary AND/OR stay eager; only if/loop conditions short-circuit.
    expect_exit 0 "$check_udewy" --target "$check_target" udewy/tests/test_guarded_calls.udewy
    expect_exit 42 "$check_dewy" --target "$check_target" "$check_work/scalar.dewy"
    expect_exit 42 "$check_dewy" --target "$check_target" tests/fixtures/native_pair_checks.dewy
    echo "Checking native test discovery with $check_target output"
    test_status=0
    test_output=$(timeout 180s "$check_dewy" test --target "$check_target" --json "$check_work/tests" 2>&1) || test_status=$?
    if [[ $test_status != 1 ||
          $test_output != *'{"passed": 3, "failed": 0}'* ||
          $test_output != *'{"passed": 0, "failed": 1}'* ||
          $test_output != *'{"files": 2, "failed_files": 1, "failed": 1}'* ]]; then
        printf '%s\n' "$test_output" >&2
        echo "Native test discovery returned $test_status or incorrect counts" >&2
        exit 1
    fi
done
echo 'Native pair execution checks passed'
