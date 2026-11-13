"""Immutable compiler source snapshots and leaf-driver templates, shared for a pytest session.

Keys include every source's text, so a changed body, an added module or a deletion makes
another template. Callers always receive a copy and may install their own service doubles.
"""
import json
import os
import re
from functools import lru_cache
from pathlib import Path

from tests.support import ROOT
from tools.core import file_stamp


@lru_cache(maxsize=2048)
def _read(path, stamp):
    return path.read_text()


def module_text(path):
    # Windows ctime is creation time, so restored-mtime edits need a fresh read.
    if os.name == 'nt':
        return path.read_text()
    return _read(path, tuple(file_stamp(path)))


def source_modules(directory):
    return tuple((p.name, module_text(p))
                 for p in Path(directory).iterdir() if p.suffix in ('.jo', '.dewy'))


def compiler_modules(leaf, directory=ROOT / 'compiler'):
    leaves = (leaf,) if isinstance(leaf, str) else tuple(leaf)
    return dict(_template(leaves, source_modules(directory)))


@lru_cache(maxsize=64)
def _template(leaves, sources):
    # Keep the real service graph: this group owns the recursive dispatcher, so
    # stubbing each outward edge would hide the execution we need to compare.
    # Switch only the requested leaf. Other twins are import shims to the live services;
    # otherwise the helper's Jo imports and Dewy's direct imports create two
    # copies of checker state. Double-quoted service imports stay fixed while
    # compare_leaf switches the single-quoted leaf import.
    # A family of leaves may be compared together (one tuple of stems, one compiler pair).
    family = '|'.join(re.escape(stem) for stem in leaves)
    modules = dict(sources)
    for name in list(modules):
        if name.endswith('.jo') and name[:-3] not in leaves:
            service_leaf = name[:-3] + '.dewy'
            if service_leaf in modules:
                modules[name] = f'use "{service_leaf}"\n'
    for name, text in list(modules.items()):
        if name.endswith('.jo'):
            modules[name] = re.sub(
                rf"(?m)^((?:use|import) )'((?!(?:{family})\.dewy)[^'\n]+\.dewy)'",
                lambda m: m[1] + json.dumps(m[2]), text)
            # Real service modules already resolve their dependencies. Keep the
            # leaf helper from inserting a test-driver initialization cycle.
            modules[name] += "\n# No use 'driver.jo' or use 'checker_resolve.dewy' needed.\n"
    # The generic leaf driver imports type modules before main, changing the
    # cycle's initializer order. Bind existing host records after all module
    # initializers have run, just before entering the compiler pipeline.
    rebind = []
    for name, text in list(modules.items()):
        if not name.endswith('.jo'):
            continue
        bindings = re.findall(r'(?m)^\w+_binding = (\w+_bind\([^\n]+\))$', text)
        if bindings:
            function = 'lower_test_bind_' + name[:-3]
            modules[name] += '\n' + function + ' = ():\n' + ''.join(
                '    ' + call + '\n' for call in bindings)
            rebind.append((name, function))
    modules['main.jo'] = ''.join(f'use "{name}"\n' for name, _ in rebind
                                 if name != 'main.jo') + modules['main.jo']
    modules['main.jo'] = modules['main.jo'].replace('main = ():',
        'lower_test_cli = ():\n' + ''.join('    ' + function + '()\n'
                                           for _, function in rebind), 1)
    return modules
