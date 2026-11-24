"""Immutable compiler source snapshots and leaf-driver templates, shared for a pytest session.

Keys include every source's text, so a changed body, an added module or a deletion makes
another template. Callers always receive a copy and may install their own service doubles.
"""
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
    # (sorted: the order a file system lists a directory in must not reach the driver's module order)
    return tuple((p.name, module_text(p))
                 for p in sorted(Path(directory).iterdir()) if p.suffix in ('.jo', '.dewy'))


def compiler_modules(directory=ROOT / 'compiler'):
    return dict(_template(source_modules(directory)))


@lru_cache(maxsize=4)
def _template(sources):
    modules = dict(sources)
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
