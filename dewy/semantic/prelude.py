"""Ordered source files implicitly available to Dewy modules.

The prelude is the portable library plus the target's *services* layer.
Target *primitives* (raw output) are imported by the portable files
themselves, gated on `$target` exactly as udewy does (see `library/io.dewy`),
so only services that also use portable types (for example `sleep` taking a
`Duration`) are listed here, after the portable files. Later prelude files
see earlier ones' bindings.
"""

import os
from pathlib import Path

project_root = Path(__file__).parents[2]
# Match the native invocation's configured library. Resolve it once before
# constructing the ordered prelude paths, so named and explicit imports of
# the same file share module and nominal-type identities.
library = Path(os.environ.get('DEWY_LIBRARY_ROOT', project_root / 'library')).resolve()

PORTABLE_LIBRARIES = (
    library / 'strings.dewy',
    library / 'arrays.dewy',
    library / 'path.dewy',
    library / 'unicode.dewy',
    library / 'math.dewy',
    library / 'rational.dewy',
    library / 'fixed.dewy',
    library / 'bigint.dewy',
    library / 'bigrational.dewy',
    library / 'io.dewy',
    library / 'reporting.dewy',
    library / 'testing.dewy',
    library / 'unicode/runtime.dewy',
    library / 'time.dewy',
    library / 'doc.dewy',
)

# Backend name (udewy's `$target`) -> services layer. Every target shares the
# runtime (`system.dewy`), which imports its operating-system hooks from the
# target's layer: Linux syscalls for the native backends and C, the host's
# imports for wasm32.
_SERVICES = (library / 'system.dewy',)
TARGET_SERVICES: dict[str, tuple[Path, ...]] = {
    'x86_64': _SERVICES,
    'arm': _SERVICES,
    'riscv': _SERVICES,
    'c': _SERVICES,
    'wasm32': _SERVICES,
}
# Services the portable libraries build on (the file system: `Path`'s
# methods call it), loaded first.
_LINUX_FOUNDATIONS = (library / 'linux' / 'files.dewy', library / 'linux' / 'process.dewy')
_WASM_FOUNDATIONS = (library / 'wasm' / 'files.dewy', library / 'wasm' / 'process.dewy')
TARGET_FOUNDATIONS: dict[str, tuple[Path, ...]] = {
    'x86_64': _LINUX_FOUNDATIONS,
    'arm': _LINUX_FOUNDATIONS,
    'riscv': _LINUX_FOUNDATIONS,
    'c': _LINUX_FOUNDATIONS,
    'wasm32': _WASM_FOUNDATIONS,
}


def prelude_files(target: str = 'x86_64') -> tuple[Path, ...]:
    return (*TARGET_FOUNDATIONS[target], *PORTABLE_LIBRARIES, *TARGET_SERVICES[target])


PRELUDE_FILES = prelude_files()
