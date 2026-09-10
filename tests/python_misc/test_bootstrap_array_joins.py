"""Branch-specific lengths remain facts about one mutable array contract."""
import subprocess

import test_bootstrap_prelude as prelude

from dewy.reporting import SrcFile
from dewy.semantic import check


def test_native_array_length_joins(tmp_path):
    binary = prelude.module_driver(tmp_path)
    for index, body in enumerate([
        'let choose=(flag:bool):>array<string>=>{let options:array<string>=[] if flag {options.push("call")} options.push("index") return options}',
        'let choose=(flag:bool):>int64=>{let values:array<int64>=[] if flag {values.push(20)} else {values.push(40) values.push(2)} values.push(22) return values.length}',
        'Box:type=[values:array<int64>]\nlet choose=(flag:bool):>int64=>{let box=Box[[]] if flag {box.values.push(20)} box.values.push(22) return box.values.length}',
        'let choose=(flag:bool):>int64=>{let values:array<int64>=[42] if flag {values[0]=20} else {values[0]=22} return values[0]}',
    ]):
        source = tmp_path / f'array-join-{index}.dewy'
        source.write_text(body)
        check.typecheck_and_resolve(SrcFile.from_path(source))
        result = subprocess.run([binary, source], capture_output=True, text=True, timeout=60, check=False)
        assert result.returncode == 0, result.stdout + result.stderr

    source = tmp_path / 'fixed-array.dewy'
    source.write_text('let choose=(flag:bool):>void=>{let values:array<int64 length=1>=[42] if flag {values[0]=20} values.push(22)}')
    result = subprocess.run([binary, source], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode != 0, result.stdout + result.stderr
