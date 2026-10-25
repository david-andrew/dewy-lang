"""Compound stores keep the old value and find the current destination after calls."""

import shutil
import subprocess

import pytest

from tests.support import Scripts, compiler, target_name  # noqa: F401


# LANGUAGE.md: selectors, then the old value, then the RHS, then a store into
# the current binding. Old 0 + RHS 0 overwrites the replacement's 100.
# Reordering and removal distinguish a fresh lookup from a stale position.
SOURCE = '''
$runtime_checks
let d:dict<string int64>=["a"->0]
replace=():>int64=>{d=["a"->100]; return 0}
apply=():>int64=>{d["a"]+=replace(); return d["a"]}
main=()=>printl(apply())
'''

CASES = {
    'reduced': (SOURCE, '0\n'),
    'main_body': (SOURCE.replace('main=()=>printl(apply())',
                                'main=()=>{d["a"]+=replace(); printl(d["a"])}'), '0\n'),
    'global_reorder': ('''
let d:dict<string int64>=["a"->10 "b"->20]
replace=():>int64=>{d=["b"->200 "a"->100]; return 7}
apply=()=>{d["a"]+=replace(); printl(d)}
main=()=>apply()
''', '["b" -> 200 "a" -> 17]\n'),
    'global_array': ('''
let d:array<int64>=[10 20]
replace=():>int64=>{d=[100 200 300]; return 7}
apply=()=>{d[0]+=replace(); printl(d)}
main=()=>apply()
''', '[17 200 300]\n'),
    'global_nested': ('''
let d:dict<string dict<string int64>>=["a"->["x"->10 "y"->20] "b"->["x"->30]]
replace=():>int64=>{d=["b"->["x"->300] "a"->["y"->200 "x"->100]]; return 7}
apply=()=>{d["a"]["x"]+=replace(); printl(d)}
main=()=>apply()
''', '["b" -> ["x" -> 300] "a" -> ["y" -> 200 "x" -> 17]]\n'),
    'global_record_dict': ('''
Box:type=[items:dict<string int64> tag:int64]
let d=Box[["a"->10 "b"->20] 1]
replace=():>int64=>{d=Box[["b"->200 "a"->100] 2]; return 7}
apply=()=>{d.items["a"]+=replace(); printl(d)}
main=()=>apply()
''', '[items=["b" -> 200 "a" -> 17] tag=2]\n'),
    'global_record_field': ('''
Box:type=[value:int64 tag:int64]
let d=Box[10 1]
replace=():>int64=>{d=Box[100 2]; return 7}
apply=()=>{d.value+=replace(); printl(d)}
main=()=>apply()
''', '[value=17 tag=2]\n'),
    'captured': ('''
main=()=>{
    let d:dict<string int64>=["a"->10 "b"->20]
    let apply=($capture @d)=>{
        let replace=($capture @d):>int64=>{d=["b"->200 "a"->100]; return 7}
        d["a"]+=replace(); printl(d)
    }
    apply(); printl(d)
}
''', '["b" -> 200 "a" -> 17]\n' * 2),
    'place_parameter': ('''
replace=(@d:dict<string int64>):>int64=>{d=["b"->200 "a"->100]; return 7}
apply=(@d:dict<string int64>)=>{d["a"]+=replace(@d); printl(d)}
main=()=>{let d:dict<string int64>=["a"->10 "b"->20]; apply(@d); printl(d)}
''', '["b" -> 200 "a" -> 17]\n' * 2),
    'place_ambient_call': ('''
let d:dict<string int64>=["a"->10 "b"->20]
replace=():>int64=>{d=["b"->200 "a"->100]; return 7}
apply=(@x:dict<string int64>)=>{x["a"]+=replace(); printl(x)}
main=()=>{apply(@d); printl(d)}
''', '["b" -> 200 "a" -> 17]\n' * 2),
    'local_block': ('''
main=()=>{
    let d:dict<string int64>=["a"->10 "b"->20]
    d["a"]+={d=["b"->200 "a"->100]; 7}
    printl(d)
}
''', '["b" -> 200 "a" -> 17]\n'),
    'selectors_once': ('''
let d:dict<string array<int64>>=["a"->[10 11] "b"->[20 21]]
let log=""
let key="a"
let index:int64=0
pick=():>string=>{log="{log}k"; return key}
at=():>int64=>{log="{log}i"; return index}
replace=():>int64=>{
    log="{log}r"; d=["b"->[200 201] "a"->[100 101]]
    key="b"; index=1; return 7
}
apply=()=>{d[pick()][at()]+=replace(); printl'{d} {log}'}
main=()=>apply()
''', '["b" -> [200 201] "a" -> [17 101]] kir\n'),
}

MODES = {'native': (), 'release': ('--release',), 'debug': ('-g',),
         'wasm': ('--target', 'wasm32'),
         'arm64': ('--target', target_name('linux-arm64'))}

# Both spellings invoke the same code. Bare selectors must also run once.
VARIANTS = [(name, 'explicit') for name in CASES]
VARIANTS += [(name, 'bare') for name, (source, _) in CASES.items() if 'replace()' in source]


@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('case,spelling', VARIANTS, ids=['-'.join(v) for v in VARIANTS])
def test_differential_dict_effect(compiler, tmp_path, mode, case, spelling):
    if mode == 'wasm' and not shutil.which('node'):
        pytest.skip('Node is needed for web execution')
    if mode == 'arm64' and not shutil.which('qemu-aarch64'):
        pytest.skip('qemu-aarch64 is needed for arm64 execution')
    source, expected = CASES[case]
    if spelling == 'bare':
        source = source.replace('+=replace()', '+=replace').replace('[pick()][at()]', '[pick][at]')
    if '$runtime_checks' not in source:
        source = '$runtime_checks\n' + source
    path = tmp_path / 'dict.dewy'
    path.write_text(source)
    binary = tmp_path / mode
    built = subprocess.run([compiler, 'build', path, '-o', binary, *MODES[mode]],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, f'{mode}: {built.stdout}{built.stderr}'
    if mode == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'wasm.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [shutil.which('node'), runner]
    elif mode == 'arm64':
        command = [shutil.which('qemu-aarch64'), binary]
    else:
        command = [binary]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=20)
    assert ran.returncode == 0, (mode, ran.stdout, ran.stderr)
    assert ran.stdout == expected, (mode, ran.stdout, expected)
