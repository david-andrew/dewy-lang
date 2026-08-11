"""udewy source backend.

The package exposes ``codegen`` as its public API. Target-specific HIR
transformation lives in ``lower`` and source rendering lives in ``emit``.
"""

from .emit import codegen, codegen_inner

__all__ = ['codegen', 'codegen_inner']
