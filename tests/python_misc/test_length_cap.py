"""The per-target length cap: an axiom the analysis trusts and `dewy analyze` reports."""
import subprocess
import sys
from pathlib import Path

import pytest

from dewy import targets
from dewy.reporting import SrcFile
from dewy.semantic import check
from dewy.semantic.analyze import bounds
from dewy.semantic.errors import UserError

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BOUNDED = 'let f = (s:string<length <=? {bound}>):>int64 => s.length\nlet g2 = (t:string):>int64 => f(t)\n'


def _check(source: str, target: str = 'x86_64') -> list[str]:
    bounds.last_cap_notes.clear()
    check.typecheck_and_resolve(SrcFile(None, source), target=target)
    return [note.message for note in bounds.last_cap_notes]


def test_the_cap_follows_the_target_address_width() -> None:
    assert targets.max_length('x86_64') == (1 << 48) - 1
    assert targets.max_length('wasm32') == (1 << 32) - 1
    assert set(targets.ADDRESS_BITS) == set(targets.TARGETS)


def test_a_length_bound_above_the_cap_holds_by_the_axiom_and_is_reported() -> None:
    notes = _check(BOUNDED.format(bound='uint64.max'))
    assert notes == ['`length <=? 18446744073709551615` holds only because lengths are assumed below 2^48 on `x86_64`']


def test_a_length_bound_below_the_cap_still_needs_a_guard() -> None:
    with pytest.raises(UserError, match='cannot prove refinement'):
        _check(BOUNDED.format(bound='uint32.max'))
    # (on `wasm32` the same bound would hold by the axiom — its cap is 2^32 — but the
    # wasm32 prelude does not build yet, so only the cap value is checked above)


def test_a_cast_that_fits_only_by_the_cap_is_reported() -> None:
    notes = _check('let total = (a:array<int64> b:array<int64>):>uint64 => {\n    let s:int64 = a.length + b.length\n    let n:uint64 = s\n    return n\n}')
    assert notes == ['fits `uint64` only because lengths are assumed below 2^48 on `x86_64`']


def test_a_proof_from_a_literal_length_does_not_rest_on_the_cap() -> None:
    assert _check('let f = (s:string<length <=? uint64.max>):>int64 => s.length\nlet n = f("ab")') == []


def test_dewy_analyze_prints_the_length_cap_report(tmp_path: Path) -> None:
    program = tmp_path / 'cap.dewy'
    program.write_text(BOUNDED.format(bound='uint64.max') + 'main = () => { printl(g2("ab"))  return 0 }\n')
    result = subprocess.run([sys.executable, '-m', 'dewy', 'analyze', str(program)], cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert 'Info: address-space cap' in result.stdout and 'assumed below 2^48 on `x86_64`' in result.stdout
    assert 'length cap report' in result.stdout and '1 proof above rest on it' in result.stdout
