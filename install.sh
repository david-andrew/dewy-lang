#!/usr/bin/env bash
# Install the published native Dewy/µDewy pair and its matching library.
set -euo pipefail

REPO='david-andrew/dewy-lang'
ASSET='dewy-linux-x86_64.tar.gz'
INSTALL_DIR="${HOME}/.dewy"
RELEASE="${DEWY_RELEASE:-latest}"
if [[ "$RELEASE" == latest ]]; then
    RELEASE_URL="https://github.com/${REPO}/releases/latest/download/${ASSET}"
else
    RELEASE_URL="https://github.com/${REPO}/releases/download/${RELEASE}/${ASSET}"
fi

os=$(uname -s)
arch=$(uname -m)
if [[ "$os" != Linux || "$arch" != x86_64 ]]; then
    echo "This installer currently supports Linux x86_64 only (got ${os} ${arch})." >&2
    exit 1
fi

temp_dir=$(mktemp -d "${TMPDIR:-/tmp}/dewy-install.XXXXXX")
install_next="${INSTALL_DIR}/.current.new.$$"
cleanup() { rm -rf -- "$temp_dir"; rm -f -- "$install_next"; }
trap cleanup EXIT

echo "Downloading ${RELEASE_URL}"
curl -fsSL "$RELEASE_URL" -o "${temp_dir}/${ASSET}"
mkdir -- "${temp_dir}/package"
tar -xzf "${temp_dir}/${ASSET}" --no-same-owner -C "${temp_dir}/package"
(
    cd -- "${temp_dir}/package"
    for required in dewy udewy VERSION SHA256SUMS library/path.dewy library/unicode/grapheme_break.bin tools/dewy_gdb.py tools/dewy_lldb.py; do
        if [[ ! -f "$required" ]]; then
            echo "Downloaded native package is missing ${required}." >&2
            exit 1
        fi
    done
    sha256sum --check --status SHA256SUMS
    test -x dewy && test -x udewy
    ./dewy --version
    ./udewy --help > /dev/null
)

# The pair and library move together. Switching one symlink makes a complete
# release active; /proc/self/exe resolves to the versioned directory, where
# native Dewy discovers its sibling compiler and matching library.
read -r release_digest _ < <(sha256sum "${temp_dir}/${ASSET}")
release_dir="${INSTALL_DIR}/releases/${release_digest}"
mkdir -p -- "${INSTALL_DIR}/releases"
if [[ ! -d "$release_dir" ]]; then
    mv -- "${temp_dir}/package" "$release_dir"
fi
ln -s -- "releases/${release_digest}" "$install_next"
mv -Tf -- "$install_next" "${INSTALL_DIR}/current"
for compiler in dewy udewy; do
    ln -sfn -- "current/${compiler}" "${INSTALL_DIR}/${compiler}"
done

path_block() {
    cat <<EOF

# Include dewy tools in PATH
if [ -d "${INSTALL_DIR}" ]; then
  PATH="${INSTALL_DIR}:\$PATH"
fi
EOF
}

already_on_path() {
    case ":${PATH}:" in
        *":${INSTALL_DIR}:"*) return 0 ;;
        *) return 1 ;;
    esac
}

append_if_missing() {
    local file=$1
    local marker=$2
    mkdir -p "$(dirname "$file")"
    if [ -f "$file" ] && grep -Fq "$marker" "$file"; then
        echo "PATH already configured in ${file}"
        return
    fi
    path_block >> "$file"
    echo "Updated ${file} to include ${INSTALL_DIR} in PATH"
}

shell_name=$(basename "${SHELL:-}")
case "$shell_name" in
    bash)
        append_if_missing "${HOME}/.bashrc" "${INSTALL_DIR}"
        if [ -f "${HOME}/.bash_profile" ]; then
            append_if_missing "${HOME}/.bash_profile" "${INSTALL_DIR}"
        elif [ -f "${HOME}/.profile" ]; then
            append_if_missing "${HOME}/.profile" "${INSTALL_DIR}"
        fi
        ;;
    zsh)
        append_if_missing "${HOME}/.zshrc" "${INSTALL_DIR}"
        append_if_missing "${HOME}/.zprofile" "${INSTALL_DIR}"
        ;;
    fish)
        fish_config="${HOME}/.config/fish/config.fish"
        mkdir -p "$(dirname "$fish_config")"
        if [ -f "$fish_config" ] && grep -Fq "$INSTALL_DIR" "$fish_config"; then
            echo "PATH already configured in ${fish_config}"
        else
            cat >> "$fish_config" <<EOF

# Include dewy tools in PATH
if test -d "${INSTALL_DIR}"
  set -gx PATH "${INSTALL_DIR}" \$PATH
end
EOF
            echo "Updated ${fish_config} to include ${INSTALL_DIR} in PATH"
        fi
        ;;
    *)
        append_if_missing "${HOME}/.profile" "${INSTALL_DIR}"
        ;;
esac

echo
echo "Installed ${INSTALL_DIR}/dewy"
echo "Installed ${INSTALL_DIR}/udewy"
if already_on_path; then
    echo "dewy and udewy are on PATH in this shell. Run: dewy --help"
else
    echo "Open a new terminal, or source your shell rc, then run: dewy --help"
fi
