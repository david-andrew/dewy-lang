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
        dewy = top_level((COMPILER / module).read_text(), r'^(?:let\s+)?([A-Za-z_]\w*)\s*[:=]')
        jo = top_level((COMPILER / twin).read_text(), r'^([A-Za-z_]\w*)\s*[:=]')
        assert jo <= dewy, f'{twin} defines {sorted(jo - dewy)}, which {module} does not'
