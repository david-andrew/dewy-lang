#!/usr/bin/env bash
# Rebuild the Dewy/µDewy compiler pair without Python and verify a fixed point.
# The seeds must already be native executables. The first Dewy seed may have
# been compiled by the hosted compiler; no hosted compiler is invoked here.
set -euo pipefail

bootstrap_target=x86_64
if [[ ${1:-} == --target ]]; then
    if [[ $# -lt 2 ]]; then
        echo '--target needs x86_64 or c' >&2
        exit 2
    fi
    bootstrap_target=$2
    shift 2
fi
if [[ $bootstrap_target != x86_64 && $bootstrap_target != c ]]; then
    echo "Unsupported native bootstrap target: $bootstrap_target" >&2
    exit 2
fi
if [[ $# -lt 2 || $# -gt 3 ]]; then
    echo "Usage: $0 [--target x86_64|c] NATIVE_DEWY_SEED NATIVE_UDEWY_SEED [OUTPUT_DIRECTORY]" >&2
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
if [[ $bootstrap_target == c ]] && ! command -v cc >/dev/null; then
    echo 'The C bootstrap accelerator needs cc on PATH' >&2
    exit 2
fi
mkdir -p -- "$bootstrap_output"
# Let the Dewy process exit before µDewy (and possibly a C compiler) starts.
# The first seed can retain a large compilation arena through emission.
# Record its exact backend arguments, then execute them after that arena is
# gone. Every real backend failure still stops the build before certification.
bootstrap_handoff=$(mktemp -d "$bootstrap_output/.backend-handoff.XXXXXX")
bootstrap_cc_tools=''
bootstrap_cleanup() {
    rm -rf -- "$bootstrap_handoff"
    if [[ -n $bootstrap_cc_tools ]]; then rm -rf -- "$bootstrap_cc_tools"; fi
}
trap bootstrap_cleanup EXIT
export DEWY_BOOTSTRAP_BACKEND_ARGS="$bootstrap_handoff/arguments"
cat > "$bootstrap_handoff/udewy" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ $# != 4 || $1 != --target || $3 != -c || ! -s $4 ]]; then
    echo 'Unexpected bootstrap backend invocation' >&2
    exit 2
fi
printf '%s\0' "$@" > "$DEWY_BOOTSTRAP_BACKEND_ARGS"
EOF
chmod +x "$bootstrap_handoff/udewy"
# Optional GCC accelerator for the large generated translation units. Keep
# the same compiler/options in both generations; byte comparison still
# decides whether the pair has reached a fixed point. Other C compilers and
# the direct backend retain the ordinary route unless explicitly selected.
bootstrap_lto_jobs=${DEWY_BOOTSTRAP_LTO_JOBS:-}
if [[ -n $bootstrap_lto_jobs ]]; then
    if [[ $bootstrap_target != c || ! $bootstrap_lto_jobs =~ ^[1-9][0-9]*$ ]]; then
        echo 'DEWY_BOOTSTRAP_LTO_JOBS needs a positive job count and --target c' >&2
        exit 2
    fi
    export DEWY_BOOTSTRAP_REAL_CC DEWY_BOOTSTRAP_CC_PATH
    DEWY_BOOTSTRAP_REAL_CC=$(command -v cc)
    DEWY_BOOTSTRAP_CC_PATH=$PATH
    bootstrap_cc_tools=$(mktemp -d "$bootstrap_output/.cc-tools.XXXXXX")
    # Check support before starting either expensive compiler generation.
    "$DEWY_BOOTSTRAP_REAL_CC" -flto="$bootstrap_lto_jobs" -x c -o "$bootstrap_cc_tools/probe" - <<'EOF'
int main(void) { return 0; }
EOF
    cat > "$bootstrap_cc_tools/cc" <<'EOF'
#!/usr/bin/env bash
# Launchers such as ccache search PATH for the underlying compiler. Exclude
# this accelerator wrapper from that search so they cannot invoke it again.
export PATH="$DEWY_BOOTSTRAP_CC_PATH"
exec "$DEWY_BOOTSTRAP_REAL_CC" "-flto=$DEWY_BOOTSTRAP_LTO_JOBS" "$@"
EOF
    chmod +x "$bootstrap_cc_tools/cc"
    export PATH="$bootstrap_cc_tools:$PATH"
fi
printf '%s\n' "$bootstrap_target" > "$bootstrap_output/BACKEND"
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
    echo "Building native compiler generation $bootstrap_generation ($bootstrap_target)"
    bootstrap_started=$SECONDS
    "$bootstrap_output/udewy-stage$bootstrap_previous" --target "$bootstrap_target" -c udewy/bootstrap/main.udewy
    cp -- __dewycache__/udewy/bootstrap/main "$bootstrap_output/udewy-stage$bootstrap_generation"
    rm -f -- "$DEWY_BOOTSTRAP_BACKEND_ARGS"
    DEWY_LIBRARY_ROOT="$bootstrap_root/library" \
        DEWY_UDEWY="$bootstrap_handoff/udewy" \
        "$bootstrap_output/dewy-stage$bootstrap_previous" --target "$bootstrap_target" -c dewy/bootstrap/main.dewy
    if [[ ! -s $DEWY_BOOTSTRAP_BACKEND_ARGS ]]; then
        echo 'The Dewy seed did not hand off a backend invocation' >&2
        exit 1
    fi
    mapfile -d '' -t bootstrap_backend_args < "$DEWY_BOOTSTRAP_BACKEND_ARGS"
    echo "Emitted Dewy generation $bootstrap_generation; building its executable"
    "$bootstrap_output/udewy-stage$bootstrap_generation" "${bootstrap_backend_args[@]}"
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
    sha256sum BACKEND dewy-stage0 dewy-stage1 dewy-stage2 dewy \
        udewy-stage0 udewy-stage1 udewy-stage2 udewy > SHA256SUMS
)
echo "Verified identical native compiler generations: $bootstrap_output"
