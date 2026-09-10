"""A loop capture collects value sites, including conditional/nested bodies."""

import subprocess

import test_bootstrap_prelude as prelude

from dewy.reporting import SrcFile
from dewy.semantic import check

CASES = [
    'let values:array<int64>=[1 2 2]\nlet selected:set<int64>=set[loop value in values if value>?1 value]',
    'let values:array<int64>=[1 2 2]\nlet selected=set[loop value in values value]',
    "let values:array<int64>=[1 2 3]\nlet selected:array<int64>=[loop value in values if value>?1 value]",
    "let values:array<int64>=[1 2]\nlet selected=[loop value in values if value>?1 value else value+1]",
    "let values:array<int64>=[1 2]\nlet selected:array<int64>=[loop value in values {let next=value+1 next}]",
    "let values:array<int64>=[1 2]\nlet selected:array<int64>=[loop left in values loop right in values if right>?left right]",
    "Segment:type=[value:int64 keep:bool]\nlet values:array<Segment>=[Segment[1 true]]\nlet selected:array<Segment>=[loop value in values if value.keep value]",
]
ERRORS = [
    "let values:array<int64>=[1 2]\nlet selected:array<string>=[loop value in values value]",
    "let values:array<int64>=[1 2]\nlet selected=[loop value in values {let unused=value}]",
]


def test_native_loop_capture(tmp_path):
    binary = prelude.module_driver(tmp_path)
    for index, text in enumerate(CASES):
        source = tmp_path / f"capture-{index}.dewy"
        source.write_text(text)
        check.typecheck_and_resolve(SrcFile.from_path(source))
        result = subprocess.run(
            [binary, source], capture_output=True, text=True, timeout=30, check=False
        )
        assert result.returncode == 0, result.stdout + result.stderr
    for index, text in enumerate(ERRORS):
        source = tmp_path / f"capture-error-{index}.dewy"
        source.write_text(text)
        result = subprocess.run(
            [binary, source], capture_output=True, text=True, timeout=30, check=False
        )
        assert result.returncode != 0, text
