"""A one-input dotted map keeps its evaluated array count through reshape."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('source,accepted', [
    ('main=()=>printl(reshape(float32.([1.0 2.0 3.0 4.0]) 2 2))', True),
    ('main=()=>{let xs=[1.0 2.0 3.0 4.0]; let ys=float32.(xs); xs.clear(); '
     'printl(reshape(ys 2 2))}', True),
    ('main=()=>printl(reshape(float32.([1.0 2.0 3.0]) 2 2))', False),
    ('probe=(xs:array<float64>)=>printl(reshape(float32.(xs) 2 2))\n'
     'main=()=>probe([1.0 2.0 3.0 4.0])', False),
])
def test_mapped_count(compiler, tmp_path, source, accepted):
    path = tmp_path / 'mapped.dewy'
    path.write_text(source + '\n')
    checked = subprocess.run([compiler, 'check', path], text=True, capture_output=True, timeout=60)
    assert (checked.returncode == 0) == accepted, checked.stdout + checked.stderr
    if not accepted:
        assert 'reshape' in checked.stderr
    else:
        output = tmp_path / 'mapped'
        built = subprocess.run([compiler, 'build', path, '-o', output], text=True,
                               capture_output=True, timeout=60)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([output], text=True, capture_output=True, timeout=10)
        assert ran.returncode == 0, ran.stdout + ran.stderr


@pytest.mark.parametrize('body', [
    'let xs:array<int>=[]; __set_len(xs 3); $assert xs.length =? 3',
    'let xs:array<int>=[]; xs.reserve(3); let snapshot=xs; '
    '__set_len(xs 3); $assert xs.length =? 3; printl(snapshot.length)',
])
def test_user_set_length_has_no_private_output_fact(compiler, tmp_path, body):
    path = tmp_path / 'set_length.dewy'
    path.write_text('main=()=>{' + body + '}\n')
    checked = subprocess.run([compiler, 'check', path], text=True, capture_output=True, timeout=60)
    assert checked.returncode != 0
    assert 'cannot prove assertion' in checked.stderr
