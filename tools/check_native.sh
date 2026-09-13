#!/usr/bin/env bash
# Exercise an already-built native pair without invoking the hosted compiler.
# Fixed-point comparison alone cannot detect a consistently miscompiled pair.
set -euo pipefail
if [[ $# -ne 1 ]]; then
    echo "Usage: $0 NATIVE_PAIR_DIRECTORY" >&2
    exit 2
fi
check_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
check_pair=$(realpath -- "$1")
check_work=$(mktemp -d "${TMPDIR:-/tmp}/dewy-native-check.XXXXXX")
trap 'rm -rf -- "$check_work"' EXIT
export DEWY_LIBRARY_ROOT="$check_root/library"
export DEWY_UDEWY="$check_pair/udewy"
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
    expect_exit 0 "$check_pair/udewy" --target "$check_target" udewy/tests/test_guarded_calls.udewy
    expect_exit 42 "$check_pair/dewy" --target "$check_target" "$check_work/scalar.dewy"
    expect_exit 42 "$check_pair/dewy" --target "$check_target" tests/fixtures/native_sibling_field_facts.dewy
    expect_exit 42 "$check_pair/dewy" --target "$check_target" tests/fixtures/native_refined_tag_tests.dewy
    expect_exit 42 "$check_pair/dewy" --target "$check_target" tests/fixtures/native_array_sharing.dewy
    expect_exit 42 "$check_pair/dewy" --target "$check_target" tests/fixtures/native_array_sharing_raw.dewy
    expect_exit 42 "$check_pair/dewy" --target "$check_target" tests/fixtures/native_borrowed_string_arrays.dewy
    expect_exit 42 "$check_pair/dewy" --target "$check_target" tests/fixtures/native_shared_element_replacement.dewy
done
echo 'Native pair execution checks passed'
