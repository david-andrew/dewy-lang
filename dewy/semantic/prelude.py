"""Ordered source files implicitly available to Dewy modules.

The prelude is the portable library plus the target's *services* layer.
Target *primitives* (raw output) are imported by the portable files
themselves, gated on `$target` exactly as udewy does (see `library/io.dewy`),
so only services that also use portable types (for example `sleep` taking a
`Duration`) are listed here, after the portable files. Later prelude files
see earlier ones' bindings.
"""

from pathlib import Path

project_root = Path(__file__).parents[2]
library = project_root / 'library'

PORTABLE_LIBRARIES = (
    library / 'path.dewy',
    library / 'math.dewy',
    library / 'rational.dewy',
    library / 'fixed.dewy',
    library / 'bigint.dewy',
    library / 'io.dewy',
    library / 'units.dewy',
)

# Backend name (udewy's `$target`) -> services layer. The native backends and
# the C backend run on the Linux syscall layer for now.
_LINUX_SERVICES = (library / 'linux' / 'system.dewy',)
TARGET_SERVICES: dict[str, tuple[Path, ...]] = {
    'x86_64': _LINUX_SERVICES,
    'arm': _LINUX_SERVICES,
    'riscv': _LINUX_SERVICES,
    'c': _LINUX_SERVICES,
    'wasm32': (),
}


def prelude_files(target: str = 'x86_64') -> tuple[Path, ...]:
    return (*PORTABLE_LIBRARIES, *TARGET_SERVICES[target])


PRELUDE_FILES = prelude_files()
