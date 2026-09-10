"""Value-copy size must not be constrained by the native machine stack."""

import subprocess
import sys

import pytest
from test_array_field_call_borrows import _build


@pytest.mark.skipif(sys.platform != "linux", reason="native Linux stack limit")
@pytest.mark.parametrize("record", [False, True])
def test_large_value_copies_use_the_frame_region(tmp_path, record):
    parameter = "bag:Bag" if record else "values:array<int64>"
    values = "bag.values" if record else "values"
    argument = "bag" if record else "bag.values"
    source = f"""Bag:type=[values:array<int64>]
let consume=({parameter}):>int64=>{{
    $runtime_assert {values}.length >? 0
    {values}[0]=42
    return {values}[0]
}}
let main=():>int64=>{{
    let bag=Bag[[]]
    loop i in 0..199999 {{bag.values.push(40)}}
    let total:int64=0
    loop i in 0..15 {{total+=consume({argument})}}
    $runtime_assert bag.values.length >? 0
    return if total=?672 and bag.values[0]=?40 42 else 1
}}
"""
    binary = _build(tmp_path, source)

    def limit_stack():
        import resource

        resource.setrlimit(resource.RLIMIT_STACK, (1024**2, 1024**2))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    result = subprocess.run(
        [binary], capture_output=True, timeout=30, check=False, preexec_fn=limit_stack
    )
    assert result.returncode == 42, result.stderr
