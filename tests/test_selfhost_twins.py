"""The compiler's Dewy modules and their frozen twins (tools/compiler/build.py): every
Dewy module has a twin, is a leaf of the compiler's import cycle, and its twin
defines nothing the Dewy module does not."""
import re
from pathlib import Path

import pytest

from tools.compiler.build import FROZEN_TWINS

COMPILER = Path(__file__).resolve().parents[1] / 'compiler'


def top_level(text, pattern):
    return {m.group(1) for m in re.finditer(pattern, text, re.M)}


@pytest.mark.core_quick
def test_every_dewy_module_has_its_twin():
    assert sorted(p.name for p in COMPILER.glob('*.dewy')) == sorted(FROZEN_TWINS)
    for module, twin in FROZEN_TWINS.items():
        assert (COMPILER / twin).is_file(), twin
        users = [p.name for p in COMPILER.glob('*.jo') if f"use '{module}'\n" in p.read_text()]
        assert users, f'no compiler module uses {module}'
        assert not [p.name for p in COMPILER.glob('*.jo') if f"use '{twin}'\n" in p.read_text()], twin


@pytest.mark.core_quick
def test_dewy_modules_are_leaves():
    stems = {p.stem for p in COMPILER.glob('*.jo')} | {p.stem for p in COMPILER.glob('*.dewy')}
    for module in FROZEN_TWINS:
        text = (COMPILER / module).read_text()
        for path in re.findall(r'^\s*(?:from|import)\s+p"([^"]+)"', text, re.M):
            assert path.startswith('@lib/'), f'{module} imports {path}: only the library'
        for name in re.findall(r'^\s*(?:from|import)\s+([A-Za-z_]\w*)', text, re.M):
            assert name not in stems, f'{module} imports the compiler module {name}'


@pytest.mark.core_quick
def test_twins_define_only_the_dewy_names():
    for module, twin in FROZEN_TWINS.items():
        dewy = top_level((COMPILER / module).read_text(), r'^(?:let\s+|const\s+)?([A-Za-z_]\w*)\s*[:=]')
        jo = top_level((COMPILER / twin).read_text(), r'^([A-Za-z_]\w*)\s*[:=]')
        assert jo <= dewy, f'{twin} defines {sorted(jo - dewy)}, which {module} does not'


def dewy_enumerations(text):
    """`Name:type = 'a' | 'b'`: each union of string literals, its members as written."""
    out = {}
    for m in re.finditer(r"^(?:let\s+)?([A-Za-z_]\w*)\s*:\s*type\s*=\s*('[^'\n]*'(?:\s*\|\s*'[^'\n]*')*)\s*$", text, re.M):
        out[m.group(1)] = re.findall(r"'([^']*)'", m.group(2))
    return out


def jo_enums(text):
    """`enum Name:` and its indented members, in order."""
    out = {}
    for m in re.finditer(r'^enum\s+([A-Za-z_]\w*)\s*:[ \t]*\n((?:[ \t]+\S.*\n?)+)', text, re.M):
        out[m.group(1)] = re.findall(r'[A-Za-z_]\w*', re.sub(r'#.*', '', m.group(2)))
    return out


@pytest.mark.core_quick
def test_twins_number_enumerations_alike():
    # (Sloppy code takes a Dewy enumeration as an enum, its members numbered as written: the
    # twin's enum lists them in the same order, so int(x) and Name(i) agree)
    for module, twin in FROZEN_TWINS.items():
        enumerations = dewy_enumerations((COMPILER / module).read_text())
        enums = jo_enums((COMPILER / twin).read_text())
        for name, members in enumerations.items():
            assert enums.get(name) == members, f'{twin} needs `enum {name}:` with {members} in order'


def test_enumeration_patterns():
    fixtures = Path(__file__).resolve().parent / 'fixtures/selfhost'
    assert dewy_enumerations((fixtures / 'enum_phase.dewy').read_text()) == {'Phase': ['lex', 'parse', 'check', 'emit']}
    assert jo_enums((fixtures / 'enum_phase.jo').read_text()) == {'Phase': ['lex', 'parse', 'check', 'emit']}
