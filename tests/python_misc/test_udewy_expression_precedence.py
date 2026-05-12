from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory

import pytest

from udewy import p0, t1
from udewy.backend import get_backend


def cc_available() -> bool:
    return which("cc") is not None


def compile_and_run(src: str, name: str) -> int | None:
    backend = get_backend("c")
    toks = t1.tokenize(src)
    code = p0.parse(toks, src, backend)

    with TemporaryDirectory() as tmp_dir_name:
        output_path = backend.compile_and_link(code, name, Path(tmp_dir_name))
        return backend.run(output_path, [])


@pytest.mark.skipif(not cc_available(), reason="cc not available")
def test_expression_precedence_and_evaluation_order() -> None:
    src = """
let seen:int = 0

let record = (n:int):>int => {
    seen = (seen * 10) + n
    return n
}

let double = (n:int):>int => {
    return n * 2
}

let choose = ():>int => {
    return double
}

let add = (a:int b:int):>int => {
    return a + b
}

let main = ():>int => {
    if 1 + 2 * 3 not=? 7 {
        return 1
    }
    if (1 + 2) * 3 not=? 9 {
        return 2
    }
    if 20 - 5 - 3 not=? 12 {
        return 3
    }
    if 1 << 2 + 1 not=? 8 {
        return 4
    }
    if (1 <? 2 and 3 <? 4 or false) not=? true {
        return 5
    }
    let piped_sum:int = 1 + 2 |> double
    if piped_sum not=? 6 {
        return 6
    }
    let piped_chain:int = 1 |> double |> double
    if piped_chain not=? 4 {
        return 7
    }
    let piped_indirect:int = 1 + 2 |> choose()
    if piped_indirect not=? 6 {
        return 8
    }
    if add(1 + 2 * 3 4 + 5 * 6) not=? 41 {
        return 9
    }

    let value:int = record(1) + record(2) * record(3)
    if value not=? 7 {
        return 10
    }
    if seen not=? 123 {
        return 11
    }

    return 0
}
"""

    assert compile_and_run(src, "expression_precedence") == 0
