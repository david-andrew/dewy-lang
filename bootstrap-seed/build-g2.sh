# Recipe v1. Run with sh from a fresh, verified extraction on Linux x86-64.
set -eu
export LC_ALL=C DEWY_EMIT_WORKERS=1 CCACHE_DISABLE=1
export DEWY_CORE_LIB=lib
mkdir bin full
for overlay in bootstrap/*.jo; do
    name=${overlay##*/}
    mv "compiler/$name" full/
    cp "$overlay" "compiler/$name"
done
make -s -C stage0 CC=gcc 'CFLAGS=-O2 -g -Wall -Wno-unused-function -Wno-sign-compare -std=gnu11'
stage0/sloppy0 compiler/main.jo -o bin/core-bootstrap
mv full/*.jo compiler/

# G1 embeds the source paths and cwd in G2. An inherited directory descriptor
# gives every private extraction the same absolute path, without a global writable
# directory or a privileged mount. G2 never needs the descriptor to run.
exec 3<.
cd /
export DEWY_CORE_LIB=/proc/self/fd/3/lib
/proc/self/fd/3/bin/core-bootstrap build /proc/self/fd/3/compiler/main.jo -o /proc/self/fd/3/bin/dewy-core-bootstrap
