"""Storage/code-generation properties that golden output cases cannot prove."""
import re
import subprocess

import pytest

from tests.support import compiler  # noqa: F401
from tests.support import target_name


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('representation', ['float32', 'float64'])
def test_quantity_kernel_erasure(compiler, tmp_path, target, release, representation):
    """An integration loop has exactly the plain-number IR in every mode.

    Keep the loop large enough that release retains it as a callable function.
    Canonical unit multiplication/division inside the loop also must disappear.
    Compare all instructions, operands, register types and stack layouts, not
    just an instruction count or the absence of a runtime tag.
    """
    bodies = []
    for quantities in (False, True):
        length = f'{representation} * Length' if quantities else representation
        speed = f'{representation} * Length / Time' if quantities else representation
        acceleration = f'{representation} * Length / Time^2' if quantities else representation
        duration = f'{representation} * Time' if quantities else representation
        reattach = 'position=(position/m)*m' if quantities else 'position=position'
        suffix = 'm' if quantities else ''
        source = tmp_path / ('quantities.dewy' if quantities else 'numbers.dewy')
        source.write_text(f'''from units import m
kernel=(position:{length} velocity:{speed} acceleration:{acceleration} step:{duration} count:int64):>({length})=>{{
    loop i in [0..count) {{
        {reattach}
        velocity+=acceleration*step
        position+=velocity*step
        velocity-=acceleration*step*0.25
        position-=velocity*step*0.125
        velocity+=acceleration*step*0.5
        position+=velocity*step*0.25
    }}
    return position
}}
main=()=>{{
    let position:{length}=1.0{suffix}
    let velocity:{speed}=2.0{'m/s' if quantities else ''}
    let acceleration:{acceleration}=0.5{'m/s^2' if quantities else ''}
    let step:{duration}=0.01{'s' if quantities else ''}
    let result=kernel(position velocity acceleration step 1000)
    printl"{{result}}"
}}
''')
        flags = ['--ir', '--target', target_name(target), *(['--release'] if release else [])]
        built = subprocess.run([compiler, 'build', source, '-o', source.with_suffix(''), *flags],
                               capture_output=True, text=True, timeout=30, check=False)
        assert built.returncode == 0, built.stdout + built.stderr
        kernel = re.search(r'^fn f_kernel_.*?\n(.*?)(?=^fn |\Z)',
                           built.stdout + built.stderr, re.M | re.S)
        assert kernel, 'kernel must remain emitted for the erasure comparison'
        bodies.append(kernel[1])
    assert bodies[0] == bodies[1], 'quantity qualifiers changed the kernel IR'
