#!/usr/bin/env bash
# Package a verified compiler pair and its matching runtime library.
set -euo pipefail
if [[ $# -ne 2 ]]; then
    echo "Usage: $0 VERIFIED_NATIVE_PAIR OUTPUT_ARCHIVE.tar.gz" >&2
    exit 2
fi
package_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
package_pair=$(realpath -- "$1")
package_archive=$(realpath -m -- "$2")
cd -- "$package_root"
sha256sum --check --status "$package_pair/SOURCE_SHA256SUMS"
(
    cd -- "$package_pair"
    sha256sum --check --status SHA256SUMS
    cmp -- dewy-stage1 dewy-stage2
    cmp -- udewy-stage1 udewy-stage2
    cmp -- dewy dewy-stage2
    cmp -- udewy udewy-stage2
)
mkdir -p -- "$(dirname -- "$package_archive")"
package_stage=$(mktemp -d "$(dirname -- "$package_archive")/.native-package.XXXXXX")
trap 'rm -rf -- "$package_stage"' EXIT
install -m 755 "$package_pair/dewy" "$package_pair/udewy" "$package_stage/"
cp -- VERSION "$package_stage/"
cp -- "$package_pair/SOURCE_SHA256SUMS" "$package_stage/BUILD_SOURCES.sha256"
mkdir -p -- "$package_stage/library" "$package_stage/tools" "$package_stage/udewy-stdlib"
# Keep private modules and generated Unicode data alongside public imports.
while IFS= read -r -d '' package_file; do
    install -D -m 644 "$package_file" "$package_stage/$package_file"
done < <(find library -type f \( -name '*.dewy' -o -name '*.bin' \) -print0)
cp -- tools/dewy_gdb.py tools/dewy_lldb.py "$package_stage/tools/"
cp -R -- udewy/stdlib/. "$package_stage/udewy-stdlib/"
(
    cd -- "$package_stage"
    find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
    tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner -czf "$package_archive" .
)
sha256sum -- "$package_archive"
