"""Native chains preserve direction checks and computed-operand bindings."""
import subprocess

import test_bootstrap_prelude as prelude

from dewy.reporting import SrcFile
from dewy.semantic import check

CASES = [
    'Span:type=[start:addr stop:addr]\ninside=(loc:Span src:string):>bool=>loc.start <=? loc.stop <=? src.length',
    'middle=(v:int64):>int64=>v\ninside=(x:int64):>bool=>0 <=? middle(x) <? 10',
    'inside=(x:int64):>bool=>0 <? x =? 5 <=? 5',
    'inside=(x:int64):>bool=>10 >? x >=? 0',
    'inside=(x:int64):>bool=>(0 <? x) =? true',
]
ERRORS = [
    ('inside=(x:int64):>bool=>0 <? x >? 10', 'changes direction'),
    ('inside=(x:int64):>bool=>x is? int64 <? 10', 'does not chain'),
    ('inside=(x:int64):>bool=>0 <? x not =? 3', 'does not chain'),
    ('inside=(x:int64):>bool=>0 <? x not <? 3', 'does not chain'),
]


def test_native_comparison_chains(tmp_path):
    binary = prelude.module_driver(tmp_path)
    for index, text in enumerate(CASES):
        source = tmp_path / f'chain-{index}.dewy'
        source.write_text(text)
        check.typecheck_and_resolve(SrcFile.from_path(source))
        result = subprocess.run([binary, source], capture_output=True, text=True, timeout=30, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
    for index, (text, diagnostic) in enumerate(ERRORS):
        source = tmp_path / f'bad-chain-{index}.dewy'
        source.write_text(text)
        result = subprocess.run([binary, source], capture_output=True, text=True, timeout=30, check=False)
        assert result.returncode != 0 and diagnostic in result.stdout + result.stderr
