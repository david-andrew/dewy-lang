"""Membership describes evaluated container values across later mutations."""
import subprocess

import test_bootstrap_prelude as prelude


def test_native_container_membership_snapshots(tmp_path):
    binary = prelude.module_driver(tmp_path)
    cases = [
        ('let a:dict<int64 int64>=[1->20]\nlet b:dict<int64 int64>=[2->22]\nlet result=a|b\nresult[1]+result[2]', True),
        ('let a:set<int64>=set[1]\nlet mutate=():>set<int64>=>{a.add(2) return set[]}\nlet result=a|mutate()\nresult.pop(1)', True),
        ('let a:set<int64>=set[1]\nlet mutate=():>set<int64>=>{a.add(2) return set[]}\nlet result=a|mutate()\nresult.pop(2)', False),
        ('let a:set<int64>=set[1 2]\nlet b:set<int64>=set[2 3]\nlet result=a&b\nresult.pop(2)', True),
        ('let a:set<int64>=set[1 2]\nlet b:set<int64>=set[2 3]\nlet result=a&b\nresult.pop(1)', False),
        ('let a:set<int64>=set[1 2]\nlet b:set<int64>=set[2]\nlet result=a-b\nresult.pop(2)', False),
    ]
    for index, (text, accepted) in enumerate(cases):
        source = tmp_path / f'snapshot-{index}.dewy'
        source.write_text(text)
        result = subprocess.run([binary, source], capture_output=True, text=True, timeout=60, check=False)
        assert (result.returncode == 0) == accepted, text + result.stdout + result.stderr
        if not accepted:
            assert 'not proven present' in result.stderr
