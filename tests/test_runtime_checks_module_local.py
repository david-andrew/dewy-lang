"""An obligation a scope opted into checking (`$runtime_checks`) is its module's
own handling, as a `$runtime_assert` is: it makes its function `panics` only for
callers in other modules, unless the scope says `$assume_local_asserts=false`."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

HELPER = '''pick=(xs:array<int64> i:int64):>int64=>{
    $runtime_checks
    return xs[i]
}
twice=(xs:array<int64> i:int64):>int64=>(pick(xs i)%1000)*2
'''


def run(compiler, tmp_path, files, *arguments):
    for name, text in files.items():
        (tmp_path / name).write_text(text)
    return subprocess.run([compiler, *arguments, 'main.dewy'], text=True, capture_output=True, timeout=60, cwd=tmp_path)


def test_same_module_needs_no_opt_in(compiler, tmp_path):
    # The module's own callers, transitively and through a handle, do not opt in.
    source = HELPER + 'apply=(f:<(xs:array<int64> i:int64):>int64> i:int64):>int64=>f([5 6 7] i)\nmain=():>void=>printl"{twice([1 2 3] 1)} {apply(@pick 2)}"\n'
    result = run(compiler, tmp_path, {'main.dewy': source}, 'run')
    assert result.returncode == 0 and result.stdout == '4 7\n', result.stdout + result.stderr


def test_same_module_check_still_runs(compiler, tmp_path):
    result = run(compiler, tmp_path, {'main.dewy': HELPER + 'main=():>void=>printl(twice([1 2 3] 5))\n'}, 'run')
    assert result.returncode == 101, result.stdout + result.stderr


def test_other_module(compiler, tmp_path):
    # A caller in another module sees `panics`, through the helper module's own callers too.
    files = {'helper.dewy': HELPER, 'main.dewy': 'from p"helper.dewy" import twice\nmain=():>void=>printl(twice([1 2 3] 1))\n'}
    result = run(compiler, tmp_path, files, 'check')
    assert result.returncode != 0, result.stderr
    assert 'main.dewy:2:23: error: calling `twice` may panic (twice -> pick: runtime check: index is in bounds' in result.stderr, result.stderr


def test_other_module_opted_in(compiler, tmp_path):
    files = {'helper.dewy': HELPER, 'main.dewy': 'from p"helper.dewy" import twice\nmain=():>void=>{\n    $runtime_checks\n    printl(twice([1 2 3] 1))\n}\n'}
    result = run(compiler, tmp_path, files, 'run')
    assert result.returncode == 0 and result.stdout == '4\n', result.stdout + result.stderr


def test_opt_out(compiler, tmp_path):
    # `$assume_local_asserts=false` makes the module's own callers prove it or opt in.
    result = run(compiler, tmp_path, {'main.dewy': '$assume_local_asserts=false\n' + HELPER + 'main=():>void=>printl(twice([1 2 3] 1))\n'}, 'check')
    assert result.returncode != 0 and 'calling `pick` may panic (pick: runtime check: index is in bounds' in result.stderr, result.stderr


def test_row_excludes_local(compiler, tmp_path):
    # A row excluding panics is a promise to every caller: a local check breaks it.
    source = HELPER + 'strict=(xs:array<int64> i:int64):>int64 & no panics=>twice(xs i)\nmain=():>void=>printl(strict([1 2 3] 1))\n'
    result = run(compiler, tmp_path, {'main.dewy': source}, 'check')
    assert result.returncode != 0 and "effect contract violation in 'strict': it may panic" in result.stderr, result.stderr


@pytest.mark.parametrize('kind', ['panic', 'runtime_checks', 'prototype'])
@pytest.mark.parametrize('call', ['twice([1 2 3] 1)', 'apply(@pick 1)'])
def test_external_handles_and_checks(compiler, tmp_path, kind, call):
    helper = HELPER
    if kind == 'panic':
        helper = helper.replace('$runtime_checks\n    return xs[i]', 'if i <? 0 {panic("negative index")}\n    return 7')
    elif kind == 'prototype':
        helper = helper.replace('$runtime_checks', '$prototype')
    caller = 'apply=(f:<(xs:array<int64> i:int64):>int64> i:int64):>int64=>f([5 6 7] i)\nmain=():>void=>printl(' + call + ')\n'
    local = run(compiler, tmp_path, {'main.dewy': helper + caller}, 'check')
    assert local.returncode == 0, local.stdout + local.stderr
    external = run(compiler, tmp_path, {'helper.dewy': helper, 'main.dewy': 'from p"helper.dewy" import (pick twice)\n' + caller}, 'check')
    assert external.returncode == 1 and 'may panic' in external.stderr, external.stdout + external.stderr


@pytest.mark.parametrize('reverse', [False, True])
def test_mixed_local_assumptions(compiler, tmp_path, reverse):
    blocks = ['if i >=? 0 {\n$assume_local_asserts=true\nprintl(xs[i])\n}',
              'if j >=? 0 {\n$assume_local_asserts=false\nprintl(xs[j])\n}']
    if reverse:
        blocks.reverse()
    source = 'pick=(xs:array<int64> i:int64 j:int64):>void=>{\n$runtime_checks\n' + '\n'.join(blocks) + '\n}\nmain=()=>pick([1] 0 0)\n'
    result = run(compiler, tmp_path, {'main.dewy': source}, 'check')
    assert result.returncode == 1 and 'calling `pick` may panic' in result.stderr, result.stdout + result.stderr


DEPENDENCY = '''dependency=(xs:array<int64> i:int64):>int64=>{
    $runtime_checks
    return xs[i]
}
'''
ACCEPTED = '''from p"dependency.dewy" import dependency
pick=(xs:array<int64> i:int64):>int64=>{
    $runtime_checks
    return dependency(xs i)
}
relay=(xs:array<int64> i:int64):>int64=>pick(xs i)
'''


def test_dependency_opt_in_is_module_local(compiler, tmp_path):
    files = {'dependency.dewy': DEPENDENCY,
             'main.dewy': ACCEPTED + 'main=()=>printl(relay([4 7] 1))\n'}
    result = run(compiler, tmp_path, files, 'run')
    assert result.returncode == 0 and result.stdout == '7\n', result.stdout + result.stderr
    files['main.dewy'] = ACCEPTED + 'main=()=>printl(relay([4 7] 2))\n'
    result = run(compiler, tmp_path, files, 'run')
    assert result.returncode == 101, result.stdout + result.stderr


def test_accepted_dependency_still_panics_outside_module(compiler, tmp_path):
    files = {'dependency.dewy': DEPENDENCY, 'helper.dewy': ACCEPTED,
             'main.dewy': 'from p"helper.dewy" import relay\nmain=()=>printl(relay([4 7] 1))\n'}
    result = run(compiler, tmp_path, files, 'check')
    assert result.returncode == 1 and 'calling `relay` may panic' in result.stderr, result.stdout + result.stderr


def test_direct_dependency_call_still_needs_opt_in(compiler, tmp_path):
    # Accepting it in pick does not authorize another function's direct call.
    files = {'dependency.dewy': DEPENDENCY,
             'main.dewy': ACCEPTED + 'main=()=>{printl(relay([4 7] 1)); printl(dependency([4 7] 1))}\n'}
    result = run(compiler, tmp_path, files, 'check')
    assert result.returncode == 1 and 'calling `dependency` may panic' in result.stderr, result.stdout + result.stderr


def test_accepted_dependency_still_violates_effect_row(compiler, tmp_path):
    files = {'dependency.dewy': DEPENDENCY,
             'main.dewy': ACCEPTED.replace('pick=(xs:array<int64> i:int64):>int64=>',
                                          'pick=(xs:array<int64> i:int64):>int64 & no panics=>')
                          + 'main=()=>printl(relay([4 7] 1))\n'}
    result = run(compiler, tmp_path, files, 'check')
    assert result.returncode == 1 and "effect contract violation in 'pick': it may panic" in result.stderr, result.stdout + result.stderr


def test_recursive_local_handling(compiler, tmp_path):
    source = '''from p"dependency.dewy" import dependency
pick=(xs:array<int64> i:int64 again:bool):>int64=>{
    $runtime_checks
    if again {return relay(xs i false)}
    return dependency(xs i)
}
relay=(xs:array<int64> i:int64 again:bool):>int64=>pick(xs i again)
main=()=>printl(relay([4 7] 1 true))
'''
    result = run(compiler, tmp_path, {'dependency.dewy': DEPENDENCY, 'main.dewy': source}, 'run')
    assert result.returncode == 0 and result.stdout == '7\n', result.stdout + result.stderr


@pytest.mark.parametrize('strict', [False, True])
def test_recursive_mixed_local_handling(compiler, tmp_path, strict):
    # A recursive component needs distinct answers: a refuses the local
    # assumption, but b explicitly accepts a's panics at its call.
    source = '''a=(xs:array<int64> i:int64 again:bool):>int64=>{
    $runtime_checks
    $assume_local_asserts=false
    if again {return b(xs i false)}
    return xs[i]
}
b=(xs:array<int64> i:int64 again:bool):>int64=>{
    $runtime_checks
    return a(xs i again)
}
'''
    call = 'a' if strict else 'b'
    result = run(compiler, tmp_path, {'main.dewy': source + 'main=()=>printl(' + call + '([4 7] 1 true))\n'}, 'run')
    if strict:
        assert result.returncode == 1 and 'calling `a` may panic' in result.stderr, result.stdout + result.stderr
    else:
        assert result.returncode == 0 and result.stdout == '7\n', result.stdout + result.stderr
        files = {'helper.dewy': source, 'main.dewy': 'from p"helper.dewy" import b\nmain=()=>printl(b([4 7] 1 true))\n'}
        result = run(compiler, tmp_path, files, 'check')
        assert result.returncode == 1 and 'calling `b` may panic' in result.stderr, result.stdout + result.stderr
