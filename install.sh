#!/usr/bin/env bash
# Install, update or roll back the Dewy toolchain.
#
#   curl -fsSL https://dewy-lang.org/install.sh | bash
#   curl -fsSL https://dewy-lang.org/install.sh | bash -s -- --release TAG
#   bash install.sh [--release TAG] [--prefix DIR] [--no-modify-path]
#
# Supports Linux x86_64/aarch64 and macOS arm64 (Windows: install.ps1) and
# needs bash, curl, tar and sha256sum or shasum. Without --release it installs
# the release named by https://dewy-lang.org/toolchain-channel.txt.
#
# Layout under PREFIX (default ~/.dewy):
#   toolchains/<release>/   immutable verified toolchains (bin/, lib/, RELEASE)
#   toolchains/current      two lines: the active and the previous release
#   bin/dewy, bin/dewy-core launchers; `dewy update` and `dewy rollback`
#   bin/udewy               explains that µDewy is retired
#   libexec/dewy-install.sh the verified installer of the active release
# A legacy installation in ~/.dewy (current/, releases/, ~/.dewy/dewy) is left
# as it is; the new launchers come first on PATH.
#
# Everything is downloaded and verified before anything changes. A new
# toolchain is staged under PREFIX/toolchains, smoke-tested, renamed into
# place and activated by atomically replacing toolchains/current; an
# interrupted or failed run leaves the previous toolchain active.
# DEWY_INSTALL_CHANNEL_URL and DEWY_INSTALL_DOWNLOAD_URL select a mirror.
set -euo pipefail

main() {
    umask 022
    local repo='david-andrew/dewy-lang'
    channel_url=${DEWY_INSTALL_CHANNEL_URL:-https://dewy-lang.org/toolchain-channel.txt}
    download_url=${DEWY_INSTALL_DOWNLOAD_URL:-https://github.com/${repo}/releases/download}
    tag_re='^dewy-[0-9]+\.[0-9]+\.[0-9]+-dev\.[0-9]{8}\.([0-9a-f]{12})$'
    name_re='^[A-Za-z0-9][A-Za-z0-9._-]*$'
    staging=''
    lock_dir=''
    trap cleanup EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM HUP

    local release='' prefix='' modify_path=1 action=install
    while [ $# -gt 0 ]; do
        case $1 in
            --release) [ $# -ge 2 ] || fail '--release needs a release tag'; release=$2; shift 2 ;;
            --release=*) release=${1#*=}; shift ;;
            --prefix) [ $# -ge 2 ] || fail '--prefix needs a directory'; prefix=$2; shift 2 ;;
            --prefix=*) prefix=${1#*=}; shift ;;
            --no-modify-path) modify_path=0; shift ;;
            --update) action=update; modify_path=0; shift ;;
            --rollback) action=rollback; shift ;;
            -h|--help) usage; return 0 ;;
            *) fail "unknown option: $1 (see --help)" ;;
        esac
    done
    if [ -n "$release" ] && ! [[ $release =~ $tag_re ]]; then
        fail "not a Dewy toolchain release tag: $release"
    fi
    if [ "$action" = rollback ] && [ -n "$release" ]; then
        fail 'rollback takes no release; it switches to the previous toolchain'
    fi

    detect_platform
    if [ "$action" != rollback ]; then
        require_tools
    fi
    if [ -z "$prefix" ]; then
        [ -n "${HOME:-}" ] || fail 'HOME is not set; choose a directory with --prefix'
        prefix="$HOME/.dewy"
    fi
    case $prefix in /*) ;; *) prefix="$PWD/$prefix" ;; esac
    while [ "${prefix%/}" != "$prefix" ] && [ "$prefix" != / ]; do prefix=${prefix%/}; done
    case $prefix in
        /) fail 'refusing to install into /' ;;
        *"
"*) fail 'the prefix must not contain a newline' ;;
    esac
    toolchains="$prefix/toolchains"

    if [ "$action" = rollback ]; then
        [ -d "$toolchains" ] || fail "no Dewy toolchains are installed in $prefix"
        acquire_lock
        rollback
        return 0
    fi

    mkdir -p -- "$toolchains" "$prefix/bin" "$prefix/libexec"
    acquire_lock
    # Leftovers from interrupted runs; the lock guarantees none is active.
    rm -rf -- "$toolchains"/.staging.* "$toolchains"/.trash.* "$toolchains"/.current.* \
        "$prefix"/bin/.dewy.* "$prefix"/bin/.dewy-core.* "$prefix"/bin/.udewy.* \
        "$prefix"/libexec/.dewy-install.sh.*
    staging=$(mktemp -d "$toolchains/.staging.XXXXXX")
    read_pointer

    # 1. Resolve the release and the digests that every download must match.
    local tag archive_sum installer_sum
    asset="dewy-core-${platform}.tar.gz"
    if [ -n "$release" ]; then
        tag=$release
        download "${download_url}/${tag}/SHA256SUMS" "$staging/SHA256SUMS"
        archive_sum=$(sums_lookup "$staging/SHA256SUMS" "$asset") || fail "SHA256SUMS of $tag does not list $asset"
        installer_sum=$(sums_lookup "$staging/SHA256SUMS" install.sh) || fail "SHA256SUMS of $tag does not list install.sh"
    else
        download "$channel_url" "$staging/channel.txt"
        parse_channel "$staging/channel.txt" || fail "invalid toolchain channel at $channel_url"
        tag=$channel_tag
        archive_sum=$(channel_lookup "$asset") || fail "the channel lists no $asset"
        installer_sum=$(channel_lookup install.sh) || fail 'the channel lists no install.sh'
    fi
    [[ $tag =~ $tag_re ]] || fail "not a Dewy toolchain release tag: $tag"
    local short=${BASH_REMATCH[1]}

    if [ "$action" = update ] && [ "$tag" = "$current_name" ]; then
        info "Dewy is up to date ($tag)."
    fi

    # 2. Download and verify the installer this release ships (the updater).
    download "${download_url}/${tag}/install.sh" "$staging/install.sh"
    check_sum "$staging/install.sh" "$installer_sum" install.sh

    # 3. Reuse a verified toolchain, or download, verify, extract and test one.
    local target="$toolchains/$tag"
    if [ -d "$target" ] && check_toolchain "$target" "$short" 2>/dev/null && smoke "$target"; then
        info "Using the installed toolchain $tag"
    else
        download "${download_url}/${tag}/${asset}" "$staging/$asset"
        check_sum "$staging/$asset" "$archive_sum" "$asset"
        extract "$staging/$asset" "$staging/unpacked"
        check_toolchain "$staging/unpacked/dewy-core" "$short" || fail "$asset is not a $platform toolchain for $tag; nothing was changed"
        smoke "$staging/unpacked/dewy-core" || fail "the downloaded toolchain failed its smoke test; nothing was changed"
        if [ -e "$target" ]; then
            mv -- "$target" "$toolchains/.trash.$tag.$$"
            rm -rf -- "$toolchains/.trash.$tag.$$"
        fi
        mv -- "$staging/unpacked/dewy-core" "$target"
    fi

    # 4. Launchers and the updater, each replaced by rename.
    write_launcher dewy
    write_launcher dewy-core
    write_udewy_shim
    replace "$staging/install.sh" "$prefix/libexec/dewy-install.sh" 755

    # 5. Activate: one rename switches the toolchain. Keep one previous one.
    local previous=$current_name
    if [ "$previous" = "$tag" ]; then previous=$previous_name; fi
    write_pointer "$tag" "$previous"
    current_name=$tag
    previous_name=$previous
    prune

    if [ "$modify_path" = 1 ] && [ -n "${HOME:-}" ]; then
        configure_path
    fi

    local revision
    revision=$(release_field "$target/RELEASE" revision)
    info "Installed Dewy toolchain $tag ($platform, revision $revision)"
    info "  compiler:  $target/bin/dewy-core"
    info "  launchers: $prefix/bin/dewy, $prefix/bin/dewy-core"
    if [ -n "$previous" ]; then
        info "  previous:  $previous (dewy rollback switches back)"
    fi
    if [ -e "$prefix/current" ] || [ -L "$prefix/current" ]; then
        info "The legacy installation in $prefix/current is unchanged; the new launchers take priority."
    fi
    case ":${PATH}:" in
        *":$prefix/bin:"*) ;;
        *) info "Open a new terminal (or add $prefix/bin to PATH), then run: dewy --help" ;;
    esac
}

usage() {
    cat <<'EOF'
Install the Dewy toolchain.

Usage: install.sh [--release TAG] [--prefix DIR] [--no-modify-path]

  --release TAG     install this release (dewy-0.0.0-dev.YYYYMMDD.<commit>)
                    instead of the one the dewy-lang.org channel names
  --prefix DIR      install into DIR instead of ~/.dewy
  --no-modify-path  do not add DIR/bin to PATH in shell startup files

Afterwards `dewy update [--release TAG]` installs a newer toolchain and
`dewy rollback` switches back to the previous one.
EOF
}

info() { printf '%s\n' "$*"; }
fail() { printf 'dewy install: %s\n' "$*" >&2; exit 1; }

cleanup() {
    if [ -n "$staging" ]; then rm -rf -- "$staging"; fi
    if [ -n "$lock_dir" ]; then rm -rf -- "$lock_dir"; fi
}

detect_platform() {
    local os arch
    os=$(uname -s)
    arch=$(uname -m)
    case "$os/$arch" in
        Linux/x86_64|Linux/amd64) platform=linux-x86_64 ;;
        Linux/aarch64|Linux/arm64) platform=linux-arm64 ;;
        Darwin/arm64) platform=macos-arm64 ;;
        Darwin/x86_64)
            # A shell running under Rosetta reports x86_64 on Apple silicon.
            if [ "$(sysctl -n sysctl.proc_translated 2>/dev/null || true)" = 1 ]; then
                platform=macos-arm64
            else
                fail 'Intel Macs are not supported; Dewy toolchains exist for Linux x86_64/aarch64, macOS arm64 and Windows x86_64.'
            fi ;;
        *) fail "unsupported host: $os $arch. Dewy toolchains exist for Linux x86_64/aarch64, macOS arm64 and Windows x86_64 (install.ps1)." ;;
    esac
}

require_tools() {
    local tool
    for tool in curl tar mktemp; do
        command -v "$tool" >/dev/null 2>&1 || fail "$tool is required"
    done
    if command -v sha256sum >/dev/null 2>&1; then
        sha256_tool=sha256sum
    elif command -v shasum >/dev/null 2>&1; then
        sha256_tool='shasum -a 256'
    else
        fail 'sha256sum or shasum is required'
    fi
}

sha256_of() {
    local line
    line=$($sha256_tool < "$1") || return 1
    printf '%s\n' "${line%% *}"
}

download() {
    curl --fail --silent --show-error --location --proto-redir '=https' \
        --connect-timeout 30 --retry 2 --output "$2" "$1" < /dev/null \
        || fail "could not download $1"
}

check_sum() {
    local actual
    actual=$(sha256_of "$1") || fail "could not hash $3"
    [ "$actual" = "$2" ] || fail "checksum mismatch for $3 (expected $2, got $actual); nothing was changed"
}

# Printable ASCII and LF only: channel and checksum files are data, never code.
plain_text() {
    [ -s "$1" ] && [ "$(LC_ALL=C tr -d '\n -~' < "$1" | wc -c)" -eq 0 ]
}

sums_lookup() {
    local line re='^([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9._-]*)$'
    plain_text "$1" || return 1
    while IFS= read -r line; do
        [[ $line =~ $re ]] || return 1
        if [ "${BASH_REMATCH[2]}" = "$2" ]; then
            printf '%s\n' "${BASH_REMATCH[1]}"
            return 0
        fi
    done < "$1"
    return 1
}

# toolchain-channel.txt, format 1 (see docs/DEVELOPMENT.md):
#   dewy-toolchain-channel 1 / release <tag> / sha256 <hex> <asset>... / end
parse_channel() {
    local line count=0 state=header sum_re='^sha256 ([0-9a-f]{64}) ([A-Za-z0-9][A-Za-z0-9._-]*)$'
    channel_tag=''
    channel_sums=''
    plain_text "$1" || return 1
    while IFS= read -r line; do
        count=$((count + 1))
        [ "$count" -le 64 ] || return 1
        case $state in
            header) [ "$line" = 'dewy-toolchain-channel 1' ] || return 1; state=release ;;
            release)
                case $line in 'release '*) channel_tag=${line#release } ;; *) return 1 ;; esac
                [[ $channel_tag =~ $tag_re ]] || return 1
                state=sums ;;
            sums)
                if [ "$line" = end ]; then
                    state=done
                elif [[ $line =~ $sum_re ]]; then
                    channel_sums="${channel_sums}${BASH_REMATCH[2]} ${BASH_REMATCH[1]}
"
                else
                    return 1
                fi ;;
            *) return 1 ;;
        esac
    done < "$1"
    [ "$state" = done ] && [ -n "$channel_sums" ]
}

channel_lookup() {
    local name sum
    while IFS=' ' read -r name sum; do
        if [ "$name" = "$1" ]; then
            printf '%s\n' "$sum"
            return 0
        fi
    done <<EOF
$channel_sums
EOF
    return 1
}

# Every member must be a regular file or directory below dewy-core/ with a
# plain name; links, absolute paths and .. are rejected before extraction.
extract() {
    local archive=$1 out=$2 name line count=0 member_re='^dewy-core(/[A-Za-z0-9_+@-][A-Za-z0-9._+@-]*)*/?$'
    LC_ALL=C tar -tzf "$archive" > "$staging/members" 2>/dev/null || fail "$asset is not a readable archive"
    LC_ALL=C tar -tvzf "$archive" > "$staging/listing" 2>/dev/null || fail "$asset is not a readable archive"
    while IFS= read -r name; do
        count=$((count + 1))
        [[ $name =~ $member_re ]] || fail "$asset contains an unexpected path: $name"
    done < "$staging/members"
    [ "$count" -gt 0 ] || fail "$asset is empty"
    while IFS= read -r line; do
        case $line in
            -*|d*) ;;
            *) fail "$asset contains a link or special file: $line" ;;
        esac
    done < "$staging/listing"
    mkdir -- "$out"
    LC_ALL=C tar -xzf "$archive" -C "$out" --no-same-owner < /dev/null || fail "could not extract $asset"
    [ -z "$(find "$out" ! -type f ! -type d | head -n 1)" ] || fail "$asset produced a link or special file"
}

release_field() {
    local key value
    while read -r key value; do
        if [ "$key" = "$2" ]; then
            printf '%s\n' "$value"
            return 0
        fi
    done < "$1"
    return 1
}

# Prints the problem and returns 1; reusing an installed toolchain probes it.
check_toolchain() {
    local dir=$1 short=$2 required host revision
    for required in bin/dewy-core lib/core/rt.jo PACKAGE.json RELEASE; do
        [ -f "$dir/$required" ] || { echo "the toolchain lacks $required" >&2; return 1; }
    done
    [ -x "$dir/bin/dewy-core" ] || { echo 'the toolchain compiler is not executable' >&2; return 1; }
    if [ "$(head -n 1 "$dir/RELEASE")" != 'dewy-toolchain-release 1' ]; then
        echo 'unrecognised toolchain RELEASE file' >&2
        return 1
    fi
    host=$(release_field "$dir/RELEASE" platform) || { echo 'RELEASE names no platform' >&2; return 1; }
    [ "$host" = "$platform" ] || { echo "the toolchain is for $host, not $platform" >&2; return 1; }
    revision=$(release_field "$dir/RELEASE" revision) || { echo 'RELEASE names no revision' >&2; return 1; }
    case $revision in
        "$short"*) ;;
        *) echo "the toolchain revision $revision does not match the release" >&2; return 1 ;;
    esac
}

# The compiler reports its version and builds and runs a tiny program, with
# no inherited DEWY_*/SLOPPY_* settings and no build tools on PATH.
smoke() {
    local compiler="$1/bin/dewy-core" work="$staging/smoke" status
    rm -rf -- "$work"
    mkdir -- "$work"
    local clean=(env -i "HOME=${HOME:-$work}" "TMPDIR=$work" PATH=/usr/bin:/bin)
    "${clean[@]}" "$compiler" --version < /dev/null > "$work/version" 2>&1 || { cat "$work/version" >&2; return 1; }
    printf 'main=()=>{let values=[20 22] return sum(values)}\n' > "$work/smoke.dewy"
    if ! (cd "$work" && "${clean[@]}" "$compiler" build "$work/smoke.dewy" -o "$work/smoke" < /dev/null > "$work/build.log" 2>&1); then
        cat "$work/build.log" >&2
        return 1
    fi
    status=0
    (cd "$work" && "${clean[@]}" "$work/smoke" < /dev/null > /dev/null 2>&1) || status=$?
    if [ "$status" -ne 42 ]; then
        printf 'smoke program exited with %s instead of 42\n' "$status" >&2
        return 1
    fi
}

acquire_lock() {
    local lock="$toolchains/.lock" owner waited=0
    while ! mkdir -- "$lock" 2>/dev/null; do
        owner=$(cat "$lock/pid" 2>/dev/null || true)
        # An installer that died leaves its lock; a lock without a pid is
        # stale once it is a minute old.
        if { [ -n "$owner" ] && ! kill -0 "$owner" 2>/dev/null; } \
                || { [ -z "$owner" ] && [ -n "$(find "$lock" -maxdepth 0 -mmin +1 2>/dev/null)" ]; }; then
            if mv -- "$lock" "$toolchains/.trash.lock.$$" 2>/dev/null; then
                rm -rf -- "$toolchains/.trash.lock.$$"
            fi
            continue
        fi
        if [ "$waited" -eq 0 ]; then
            info "Waiting for another Dewy installation to finish ($lock)"
        fi
        [ "$waited" -lt 600 ] || fail "timed out waiting for $lock"
        sleep 1
        waited=$((waited + 1))
    done
    lock_dir=$lock
    printf '%s\n' "$$" > "$lock/pid"
}

read_pointer() {
    current_name=''
    previous_name=''
    if [ -f "$toolchains/current" ]; then
        { IFS= read -r current_name || :; IFS= read -r previous_name || :; } < "$toolchains/current"
    fi
    [[ $current_name =~ $name_re ]] || current_name=''
    [[ $previous_name =~ $name_re ]] || previous_name=''
}

write_pointer() {
    local next="$toolchains/.current.$$"
    [ ! -d "$toolchains/current" ] || fail "$toolchains/current is a directory"
    printf '%s\n%s\n' "$1" "$2" > "$next"
    mv -f -- "$next" "$toolchains/current"
}

rollback() {
    read_pointer
    [ -n "$current_name" ] || fail "no Dewy toolchain is active in $prefix"
    if [ -z "$previous_name" ] || [ ! -x "$toolchains/$previous_name/bin/dewy-core" ]; then
        fail "there is no previous toolchain to roll back to (active: $current_name)"
    fi
    write_pointer "$previous_name" "$current_name"
    info "Rolled back to $previous_name (from $current_name; dewy rollback switches again)."
}

# Keep the active and the previous toolchain; rename others away first so
# that a half-deleted toolchain is never mistaken for a complete one.
prune() {
    local dir name
    for dir in "$toolchains"/*; do
        [ -d "$dir" ] || continue
        name=${dir##*/}
        if [ "$name" = "$current_name" ] || [ "$name" = "$previous_name" ]; then
            continue
        fi
        if mv -- "$dir" "$toolchains/.trash.$name.$$" 2>/dev/null; then
            rm -rf -- "$toolchains/.trash.$name.$$" || true
        fi
    done
}

replace() {
    local next
    next="$(dirname "$2")/.$(basename "$2").$$"
    cp -- "$1" "$next"
    chmod "$3" "$next"
    mv -f -- "$next" "$2"
}

sh_quote() {
    printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"
}

write_launcher() {
    local root
    root=$(sh_quote "$prefix")
    cat > "$staging/launcher" <<EOF
#!/bin/sh
# Dewy launcher written by the Dewy installer: runs the active toolchain's
# compiler. \`$1 update [--release TAG]\` and \`$1 rollback\` manage toolchains.
root=$root
case \${1-} in
    update|rollback)
        action=\$1
        shift
        exec bash "\$root/libexec/dewy-install.sh" "--\$action" --prefix "\$root" "\$@" ;;
esac
current=
if [ -r "\$root/toolchains/current" ]; then
    IFS= read -r current < "\$root/toolchains/current" || :
fi
case \$current in
    ''|.*|*/*)
        echo "$1: no Dewy toolchain is active in \$root; run the installer again" >&2
        exit 1 ;;
esac
exec "\$root/toolchains/\$current/bin/dewy-core" "\$@"
EOF
    replace "$staging/launcher" "$prefix/bin/$1" 755
}

write_udewy_shim() {
    local legacy
    legacy=$(sh_quote "$prefix/udewy")
    cat > "$staging/udewy" <<EOF
#!/bin/sh
# Written by the Dewy installer: µDewy is retired.
legacy=$legacy
echo 'udewy: µDewy has been retired; use dewy (dewy --help).' >&2
if [ -x "\$legacy" ]; then
    echo "The previously installed µDewy is still available as: \$legacy" >&2
fi
exit 1
EOF
    replace "$staging/udewy" "$prefix/bin/udewy" 755
}

block_start='# >>> dewy toolchain >>>'
block_end='# <<< dewy toolchain <<<'

# Replace this installer's marked block (or append one) at the end of a
# startup file, after any legacy ~/.dewy PATH line, so it takes priority.
update_rc() {
    local file=$1 block=$2 stripped="$staging/rc.stripped" next="$staging/rc.next"
    mkdir -p -- "$(dirname "$file")"
    if [ -f "$file" ]; then
        awk -v s="$block_start" -v e="$block_end" '
            !skip && $0 == s { skip = 1; held = ""; next }
            skip { if ($0 == e) { skip = 0 } else { held = held $0 "\n" }; next }
            { print }
            END { if (skip) printf "%s\n%s", s, held }' "$file" > "$stripped"
    else
        : > "$stripped"
    fi
    {
        cat "$stripped"
        if [ -s "$stripped" ] && [ -n "$(tail -n 1 "$stripped")" ]; then echo; fi
        printf '%s\n' "$block"
    } > "$next"
    if [ -f "$file" ] && cmp -s "$next" "$file"; then
        info "PATH is already configured in $file"
        return 0
    fi
    cat "$next" > "$file"
    info "Added $prefix/bin to PATH in $file"
}

configure_path() {
    local bin="$prefix/bin" quoted block
    case $bin in
        *:*) info "Not changing PATH: $bin contains ':'"; return 0 ;;
    esac
    quoted=$(sh_quote "$bin")
    block="$block_start
# Added by the Dewy installer: keep the Dewy launchers first on PATH.
case \"\$PATH\" in
    $quoted|$quoted:*) ;;
    *) PATH=$quoted:\$PATH; export PATH ;;
esac
$block_end"
    case $(basename "${SHELL:-sh}") in
        bash)
            update_rc "$HOME/.bashrc" "$block"
            if [ -f "$HOME/.bash_profile" ]; then
                update_rc "$HOME/.bash_profile" "$block"
            elif [ -f "$HOME/.profile" ]; then
                update_rc "$HOME/.profile" "$block"
            fi ;;
        zsh)
            update_rc "${ZDOTDIR:-$HOME}/.zshrc" "$block"
            update_rc "${ZDOTDIR:-$HOME}/.zprofile" "$block" ;;
        fish)
            quoted="'$(printf '%s' "$bin" | sed -e 's/\\/\\\\/g' -e "s/'/\\\\'/g")'"
            update_rc "${XDG_CONFIG_HOME:-$HOME/.config}/fish/config.fish" "$block_start
# Added by the Dewy installer: keep the Dewy launchers first on PATH.
if test \"\$PATH[1]\" != $quoted
    set -gx PATH $quoted \$PATH
end
$block_end" ;;
        *) update_rc "$HOME/.profile" "$block" ;;
    esac
}

main "$@"
