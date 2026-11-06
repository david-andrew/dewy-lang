"""Link one lowering leaf or its twin against the real compiler services."""
import json
import hashlib
import os
import re
import subprocess

from tests.support import ROOT


class CompilerModules(dict):
    """Compiler sources plus the invocation supplied to each fresh driver process."""

    def __init__(self, modules, source, output, flags):
        super().__init__(modules)
        self.arguments = ('build', str(source), '-o', str(output), *flags)

    def runtime_driver(self, driver):
        # Paths are inputs to the compiler being tested, not inputs to its build.
        for index in (2, 4):
            driver = driver.replace(json.dumps(self.arguments[index - 1]), f'args()[{index}]')
        return driver


def cached_driver(compiler, tmp_path, release, modules):
    """Reuse byte-identical builds within this pytest worker's temporary session.

    Hash the entire supplied graph, including service doubles and the driver.
    A changed leaf body therefore cannot reuse its previous executable. Runtime
    inputs and outputs stay in each test's own directory and are never cached.
    """
    identity = hashlib.sha256(compiler.read_bytes())
    identity.update(json.dumps([release, sorted((k, v) for k, v in os.environ.items()
                                               if k.startswith('DEWY_'))]).encode())
    library = os.environ.get('DEWY_CORE_LIB')
    if library:
        from pathlib import Path
        for path in sorted(Path(library).rglob('*')):
            if path.is_file():
                identity.update(str(path).encode() + b'\0' + path.read_bytes())
    for name, text in sorted(modules.items()):
        identity.update(name.encode() + b'\0' + text.encode() + b'\0')
    directory = tmp_path.parent / 'selfhost-builds' / identity.hexdigest()
    binary = directory / 'driver'
    if not (directory / 'ready').exists():
        directory.mkdir(parents=True, exist_ok=True)
        for name, text in modules.items():
            (directory / name).write_text(text)
        built = subprocess.run([compiler, 'build', directory / 'driver.jo', '-o', binary,
                                *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        (directory / 'ready').touch()
    return binary


def modules_for(source, output, leaf="lower_group", flags=()):
    # Keep the real service graph: this group owns the recursive dispatcher, so
    # stubbing each outward edge would hide the execution we need to compare.
    # Switch only the requested leaf. Other twins are import shims to the live services;
    # otherwise the helper's Jo imports and Dewy's direct imports create two
    # copies of checker state. Double-quoted service imports stay fixed while
    # compare_leaf switches the single-quoted leaf import.
    # A family of leaves may be compared together (one tuple of stems, one compiler pair).
    leaves = (leaf,) if isinstance(leaf, str) else tuple(leaf)
    family = '|'.join(re.escape(stem) for stem in leaves)
    modules = {p.name: p.read_text() for p in (ROOT / 'compiler').iterdir()
               if p.suffix in ('.jo', '.dewy')}
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
    return CompilerModules(modules, source, output, flags)
