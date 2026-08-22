#!/usr/bin/env bash
# Install the udewy bootstrap compiler into ~/.dewy.
set -euo pipefail

REPO='david-andrew/dewy-lang'
UDEWY_ASSET='udewy-linux-x86_64'
INSTALL_DIR="${HOME}/.dewy"
UDEWY_URL="https://github.com/${REPO}/releases/latest/download/${UDEWY_ASSET}"

os=$(uname -s)
arch=$(uname -m)
if [ "$os" != 'Linux' ] || [ "$arch" != 'x86_64' ]; then
    echo "This installer currently supports Linux x86_64 only (got ${os} ${arch})." >&2
    exit 1
fi

temp_dir=$(mktemp -d "${TMPDIR:-/tmp}/udewy-install.XXXXXX")
cleanup() {
    rm -rf "$temp_dir"
}
trap cleanup EXIT

echo "Downloading ${UDEWY_URL}"
if ! curl -fsSL "$UDEWY_URL" -o "${temp_dir}/udewy"; then
    echo "Failed to download udewy. Is there a published release at https://github.com/${REPO}/releases ?" >&2
    exit 1
fi

mkdir -p "$INSTALL_DIR"
install -m 755 "${temp_dir}/udewy" "${INSTALL_DIR}/udewy"

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
if test -d ${INSTALL_DIR}
  set -gx PATH ${INSTALL_DIR} \$PATH
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
echo "Installed ${INSTALL_DIR}/udewy"
if already_on_path; then
    echo "udewy is on PATH in this shell. Run: udewy --help"
else
    echo "Open a new terminal, or source your shell rc, then run: udewy --help"
fi
