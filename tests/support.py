"""Helpers shared by the pytest suites: the compiler under test and batched builds.

Simple programs belong in tests/cases (one golden file each); these helpers
serve tests that generate programs or check more than output and exit codes.
"""
import os
import platform
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def target_name(mode):
    """The compiler's --target name for a test mode; native is this machine's processor."""
    if mode == 'native':
        machine = platform.machine().lower()
        return {'amd64': 'x86_64', 'arm64': 'aarch64'}.get(machine, machine)
    return {'wasm': 'wasm32', 'linux-arm64': 'aarch64-linux', 'macos': 'aarch64-mac',
            'windows': 'x86_64-windows'}.get(mode, mode)


def case_source(name):
    """The source of the golden case tests/cases/<name>.dewy."""
    return (ROOT / 'tests' / 'cases' / f'{name}.dewy').read_text()


@pytest.fixture(scope='module')
def compiler():
    value = os.environ.get('DEWY_CORE_COMPILER')
    if not value:
        pytest.skip('set DEWY_CORE_COMPILER to the experimental source-level core')
    return Path(value).resolve(strict=True)

class Scripts(HTMLParser):
    """Extract the generated web runner, which also supports Node execution."""

    def __init__(self):
        super().__init__()
        self.inside = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.inside = True

    def handle_endtag(self, tag):
        if tag == 'script':
            self.inside = False

    def handle_data(self, data):
        if self.inside:
            self.parts.append(data)

def build_case_batch(compiler, directory, cases, body, release, target, *, arguments=False):
    """Build independent source modules with a caller-supplied test entry point."""
    imports = []
    for i, (name, source) in enumerate(cases.items()):
        (directory / f'{name}.dewy').write_text(source)
        imports.append(f'from p"{name}.dewy" import (main as case_{i})')
    source = directory / 'batch.dewy'
    parameters = 'argv:array<string>' if arguments else ''
    source.write_text('\n'.join(imports) + f'\nmain=({parameters}):>void=>{{\n'
                      + '\n'.join(body) + '\n}\n')
    binary = directory / 'batch'
    flags = ['--release'] if release else []
    if target == 'wasm':
        flags += ['--target', 'wasm32']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30, check=False)
    if built.returncode:
        message = f'Batch build failed; sources in {directory}\n{built.stdout}{built.stderr}'
        return None, message
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if node is None:
            pytest.skip('Node is needed to execute the generated web runner')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = directory / 'batch.cjs'
        prefix = 'const sloppyArgs = process.argv.slice(1);\n' if arguments else ''
        runner.write_text(prefix + '\n'.join(scripts.parts))
        command = [node, runner]
    return command, None

def isolate_value_batch_failure(compiler, directory, cases, release, target, failure):
    """Split only failed batches; retain failures that require a combined program."""
    names = list(cases)
    original = {name: (None, failure) for name in names}
    if len(names) <= 1:
        return original
    middle = len(names) // 2
    outcomes = {}
    for index, subset in enumerate((names[:middle], names[middle:])):
        part = directory / f'part-{index}'
        part.mkdir()
        outcomes.update(run_value_batch(compiler, part, {name: cases[name] for name in subset},
                                        release, target))
    # An optimizer or module-interaction bug may disappear when split. A
    # failing combined program must never become a passing validation gate.
    if all(code is not None for code, _ in outcomes.values()):
        return original
    return outcomes

def run_value_batch(compiler, directory, cases, release, target):
    """Keep source modules independent while amortizing compiler/runtime startup."""
    names = list(cases)
    body = []
    for i, name in enumerate(names):
        body.extend([f'printl"__DEWY_CASE_BEGIN__:{name}"',
                     f'let result_{i}=case_{i}()',
                     f'printl"__DEWY_CASE_END__:{name}:{{result_{i}}}"'])
    command, failure = build_case_batch(compiler, directory, cases, body, release, target)
    if failure:
        return isolate_value_batch_failure(compiler, directory, cases, release, target, failure)
    if target == 'native':
        command = [*command, 'extra']
    ran = subprocess.run(command, capture_output=True, timeout=10, check=False)
    # Decode without text-mode newline translation: string tests also verify
    # carriage returns and other control characters in the program's output.
    stdout = ran.stdout.decode('utf-8', errors='replace')
    stderr = ran.stderr.decode('utf-8', errors='replace')
    if ran.returncode:
        message = f'Batch exited {ran.returncode}; sources in {directory}\n{stdout}{stderr}'
        return isolate_value_batch_failure(compiler, directory, cases, release, target, message)
    outcomes = {}
    active, output = None, []
    for line in stdout.splitlines(keepends=True):
        if line.startswith('__DEWY_CASE_BEGIN__:'):
            active = line.strip().removeprefix('__DEWY_CASE_BEGIN__:')
            output = []
        elif line.startswith('__DEWY_CASE_END__:'):
            name, code = line.strip().removeprefix('__DEWY_CASE_END__:').rsplit(':', 1)
            if name == active:
                outcomes[name] = (code, ''.join(output))
            active = None
        elif active is not None:
            output.append(line)
    for name in names:
        if name not in outcomes:
            message = f'Missing result for {name}; sources in {directory}\n{stdout}{stderr}'
            return isolate_value_batch_failure(compiler, directory, cases, release, target, message)
    return outcomes

def build_exit_batch(compiler, directory, cases, release, target):
    # One selected case per fresh process: a panic must not prevent the other
    # cases from executing, and a normal return must remain a normal return.
    body = ['if argv.length not=? 2 panic("missing test selector")']
    body.extend(f'if argv[1] =? "{i}" {{case_{i}() return}}' for i in range(len(cases)))
    body.append('panic("invalid test selector")')
    return build_case_batch(compiler, directory, cases, body, release, target, arguments=True)
