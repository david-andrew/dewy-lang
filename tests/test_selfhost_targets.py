"""compiler/targets.dewy, the target names: it ships, and its frozen implementation-language
twin compiler/targets.jo gives the same answers. The oracle is docs/LANGUAGE.md's "Targets"
(the names, the supported ones, the processors and systems) and the messages below."""
import re
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/selfhost'
HOSTS = ['x86_64-linux', 'aarch64-linux', 'aarch64-mac', 'x86_64-windows']
OLD = {'native': None, 'linux': '; Linux on x86-64 is x86_64-linux',
       'linux-arm64': '; Linux on 64-bit ARM is aarch64-linux', 'arm': '; Linux on 64-bit ARM is aarch64-linux',
       'arm64': '; Linux on 64-bit ARM is aarch64-linux', 'macos': "; macOS on Apple's processors is aarch64-mac",
       'mac': "; macOS on Apple's processors is aarch64-mac", 'windows': '; Windows on x86-64 is x86_64-windows',
       'wasm': '; WebAssembly is wasm32', 'web': '; WebAssembly is wasm32'}


def documented():
    """The names, supported names, processors and systems docs/LANGUAGE.md lists."""
    text = (ROOT / 'docs/LANGUAGE.md').read_text()
    section = text[text.index('`--target` and `$target` use the design'):]
    table = section[section.index('| Names |'):]
    table = table[:table.index('\n\n')]
    names = {n for row in table.splitlines()[2:] for n in re.findall(r'`([^`]+)`', row.split('|')[1])}
    builds = section[section.index('This compiler builds'):section.index('the default is this machine')]
    arches = section[section.index('`$target.arch` is'):section.index('and `$target.os`')]
    oses = section[section.index('and `$target.os`'):section.index('for `wasm32` and `c89`')]
    return names, re.findall(r'`([^`]+)`', builds), re.findall(r'`([^`]+)`', arches)[1:], re.findall(r'`([^`]+)`', oses)[1:]


def arch_of(name):
    return 'c' if name == 'c89' else name.split('-', 1)[0]


def os_of(name):
    return name.split('-', 1)[1] if '-' in name else 'none'


def problem(name, host, names, supported):
    listed = ', '.join(supported)
    if name in supported:
        return ''
    if name in names:
        if name == arch_of(host):
            return ''
        if f'{name}-linux' in supported:
            return f"target '{name}' (a processor alone) means this machine, which is {host}: name the system too, as {name}-linux"
        return f"target '{name}' is not supported yet (the supported targets are {listed})"
    old = OLD.get(name, '')
    if name == 'native':
        old = f'; the current machine is the default, or its processor names it: {arch_of(host)}'
    return f"unknown target '{name}' (the supported targets are {listed}){old}"


def build(compiler, source, binary, release):
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    return binary


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_targets_matches_jo(compiler, tmp_path, release):
    names, supported, arches, oses = documented()
    words = sorted(names) + list(OLD) + ['', '-', 'a-', '-b', 'x-y-z', 'x86_64-linux-gnu', 'X86_64-LINUX',
                                         'x-é', 'é-x', 'café', 'c89-', 'wasm32-wasi']
    dewy = build(compiler, FIXTURES / 'targets_dewy.dewy', tmp_path / 'targets-dewy', release)
    jo = build(compiler, FIXTURES / 'targets_jo.jo', tmp_path / 'targets-jo', release)
    outputs = []
    for binary in (dewy, jo):
        ran = subprocess.run([binary, *words], capture_output=True, timeout=60)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    lines = outputs[0].decode().splitlines()
    tables = [line.split(' ') for line in lines[:4]]
    assert set(tables[0]) == names and len(tables[0]) == len(names)
    assert tables[1] == supported
    assert sorted(tables[2]) == sorted(arches) and sorted(tables[3]) == sorted(oses)
    expected = []
    for word in words:
        expected.append(f'{word}|{arch_of(word)}|{os_of(word)}')
        expected += [f'  {host}|{problem(word, host, names, supported)}' for host in HOSTS]
    assert lines[4:] == expected


@pytest.mark.core_quick
def test_selfhost_targets_ships_dewy(compiler, tmp_path):
    binary = compiler.read_bytes()
    assert b'/compiler/targets.dewy\0' in binary
    assert b'/compiler/targets.jo\0' not in binary
    source = tmp_path / 'hello.dewy'
    source.write_text('main=():>void=>printl"hi"\n')
    built = subprocess.run([compiler, 'build', source, '--target', 'arm64'], capture_output=True, text=True, timeout=60)
    assert built.returncode != 0
    assert ("unknown target 'arm64' (the supported targets are x86_64-linux, aarch64-linux, aarch64-mac, "
            'x86_64-windows, wasm32); Linux on 64-bit ARM is aarch64-linux') in built.stdout + built.stderr
