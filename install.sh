#!/usr/bin/env bash
# Install udewy and the Python-backed dewy compiler into ~/.dewy.
set -euo pipefail

REPO='david-andrew/dewy-lang'
REPO_REF="${DEWY_REF:-master}"
UDEWY_ASSET='udewy-linux-x86_64'
INSTALL_DIR="${HOME}/.dewy"
RUNTIME_DIR="${INSTALL_DIR}/runtime"
UDEWY_URL="https://github.com/${REPO}/releases/latest/download/${UDEWY_ASSET}"
SOURCE_URL="https://github.com/${REPO}/archive/refs/heads/${REPO_REF}.tar.gz"

os=$(uname -s)
arch=$(uname -m)
if [ "$os" != 'Linux' ] || [ "$arch" != 'x86_64' ]; then
    echo "This installer currently supports Linux x86_64 only (got ${os} ${arch})." >&2
    exit 1
fi

temp_dir=$(mktemp -d "${TMPDIR:-/tmp}/dewy-install.XXXXXX")
runtime_next="${INSTALL_DIR}/.runtime.new.$$"
runtime_old="${INSTALL_DIR}/.runtime.old.$$"

cleanup() {
    rm -rf "$temp_dir" "$runtime_next"
}
trap cleanup EXIT

echo "Downloading ${UDEWY_URL}"
if ! curl -fsSL "$UDEWY_URL" -o "${temp_dir}/udewy"; then
    echo "Failed to download udewy. Is there a published release at https://github.com/${REPO}/releases ?" >&2
    exit 1
fi

echo "Downloading Dewy Python sources from ${SOURCE_URL}"
if ! curl -fsSL "$SOURCE_URL" -o "${temp_dir}/source.tar.gz"; then
    echo "Failed to download the Dewy Python sources." >&2
    exit 1
fi

mkdir -p "${temp_dir}/source" "${temp_dir}/runtime"
if ! tar -xzf "${temp_dir}/source.tar.gz" --strip-components=1 -C "${temp_dir}/source"; then
    echo "Failed to unpack the Dewy Python sources." >&2
    exit 1
fi

source_dir="${temp_dir}/source"
runtime_stage="${temp_dir}/runtime"
for required_path in VERSION dewy/__main__.py udewy/__main__.py library/path.dewy library/io.dewy; do
    if [ ! -f "${source_dir}/${required_path}" ]; then
        echo "Downloaded source archive is missing ${required_path}." >&2
        exit 1
    fi
done

copy_runtime_file() {
    local source_file=$1
    local relative_path=${source_file#"${source_dir}/"}
    mkdir -p "${runtime_stage}/$(dirname "$relative_path")"
    cp "$source_file" "${runtime_stage}/${relative_path}"
}

# Dewy's compiler is all Python. Its tests, docs, and sample programs are not
# needed at runtime, so only Python modules and the two implicit library files
# are installed. udewy's Python runtime has a smaller, explicit module set.
while IFS= read -r -d '' source_file; do
    copy_runtime_file "$source_file"
done < <(
    find "${source_dir}/dewy" \
        -type f -name '*.py' \
        ! -path "${source_dir}/dewy/tests/*" \
        ! -path "${source_dir}/dewy/todo.py" \
        ! -path "${source_dir}/dewy/semantic/unicode/generate.py" \
        -print0
)

for source_file in \
    "${source_dir}"/udewy/*.py \
    "${source_dir}"/udewy/backend/*.py \
    "${source_dir}"/udewy/third_party/sdl/desktop_launch.py; do
    if [ -f "$source_file" ]; then
        copy_runtime_file "$source_file"
    fi
done

copy_runtime_file "${source_dir}/VERSION"
copy_runtime_file "${source_dir}/library/path.dewy"
copy_runtime_file "${source_dir}/library/io.dewy"
if [ -f "${source_dir}/assets/udewy_logo_128x128.png" ]; then
    copy_runtime_file "${source_dir}/assets/udewy_logo_128x128.png"
fi

cat > "${temp_dir}/dewy" <<'LAUNCHER'
#!/bin/sh
set -eu

dewy_home=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
dewy_runtime="${dewy_home}/runtime"
python_marker="${dewy_home}/.python-3.12-ok"

if [ ! -f "${dewy_runtime}/dewy/__main__.py" ]; then
    echo "Dewy runtime not found at ${dewy_runtime}. Re-run the Dewy installer." >&2
    exit 1
fi

run_dewy() {
    DEWY_PYTHON=$1
    shift
    export PYTHONPATH="${dewy_runtime}${PYTHONPATH:+:${PYTHONPATH}}"
    exec "$DEWY_PYTHON" -m dewy "$@"
}

# A successful first-run check records the interpreter path. Reading this file
# avoids starting Python once just to check its version on every later run.
if [ -r "$python_marker" ]; then
    IFS= read -r cached_python < "$python_marker" || cached_python=''
    if [ -n "$cached_python" ] && [ -x "$cached_python" ]; then
        run_dewy "$cached_python" "$@"
    fi
fi

found_python=false
for python_command in python3 python; do
    python_path=$(command -v "$python_command" 2>/dev/null || true)
    if [ -z "$python_path" ]; then
        continue
    fi
    found_python=true
    if "$python_path" -c 'import sys; raise SystemExit(sys.version_info < (3, 12))'; then
        marker_temp="${python_marker}.tmp.$$"
        if printf '%s\n' "$python_path" > "$marker_temp"; then
            mv "$marker_temp" "$python_marker"
        else
            rm -f "$marker_temp"
        fi
        run_dewy "$python_path" "$@"
    fi
done

if [ "$found_python" = true ]; then
    echo "Dewy requires Python 3.12 or newer; no compatible Python interpreter was found." >&2
else
    echo "Dewy requires Python 3.12 or newer, but Python was not found." >&2
fi
exit 1
LAUNCHER

mkdir -p "$INSTALL_DIR"
rm -rf "$runtime_next" "$runtime_old"
cp -R "$runtime_stage" "$runtime_next"
if [ -d "$RUNTIME_DIR" ]; then
    mv "$RUNTIME_DIR" "$runtime_old"
    if mv "$runtime_next" "$RUNTIME_DIR"; then
        rm -rf "$runtime_old"
    else
        mv "$runtime_old" "$RUNTIME_DIR"
        echo "Failed to update ${RUNTIME_DIR}; the previous runtime was restored." >&2
        exit 1
    fi
else
    mv "$runtime_next" "$RUNTIME_DIR"
fi
install -m 755 "${temp_dir}/udewy" "${INSTALL_DIR}/udewy"
install -m 755 "${temp_dir}/dewy" "${INSTALL_DIR}/dewy"

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
echo "Installed ${INSTALL_DIR}/dewy"
echo "Installed ${INSTALL_DIR}/udewy"
if already_on_path; then
    echo "dewy and udewy are on PATH in this shell. Run: dewy --help"
else
    echo "Open a new terminal, or source your shell rc, then run: dewy --help"
fi
