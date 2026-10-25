"""secret<T> (compiler/secrets.jo): zero-cost, and redacted where cases cannot look: the code is
the plain program's, `main`'s error report (also with -g), runtime-check reports, editor hovers
and the debugger. (The language rules: tests/cases/secret.)"""
import re
import shutil
import subprocess

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_core_editor import Client

# One program, written with secrets (`@S<T>` and `.@R`) and without: the IR must be the same.
PROBE = '''Login:type = [user:string pass:@S<string>]
check = (pw:@S<string> attempt:string):>bool => pw =? attempt
scale = (k:@S<int64> x:int64):>@S<int64> => k * x + 7
total = (ks:array<@S<int64>>):>@S<int64> => {
    let t:@S<int64> = 0
    loop k in ks { t = t + k }
    t
}
lookup = (vault:dict<@S<string> int64> key:@S<string>):>int64 => if vault.has(key) vault[key] else -1
pick = (o:@S<float64>?):>float64 => if o is? none 0.0 else o.@R * 2.0
bump = (@k:@S<int64>):>void => { k += 1 }
main = () => {
    let a = args()
    if a.length <? 2 return
    let l = Login["ann" "pw"]
    printl(check(l.pass a[1]))
    printl(scale(a.length a.length).@R)
    printl(total([1 2 3]).@R)
    let vault:dict<@S<string> int64> = ["pw" -> 7]
    printl(lookup(vault l.pass))
    let o:@S<float64>? = 1.5
    printl(pick(o))
    let n:@S<int64> = 41
    bump(@n)
    printl(n.@R)
}
'''


def probe(secret):
    if secret:
        return PROBE.replace('@S<', 'secret<').replace('.@R', '.reveal')
    return re.sub(r'@S<([^<>]*)>', r'\1', PROBE).replace('.@R', '')


def run(command, **kwargs):
    return subprocess.run([str(c) for c in command], capture_output=True, text=True, timeout=120, **kwargs)


@pytest.mark.parametrize('flags', [(), ('--release',), ('--target', 'wasm32')])
def test_secret_code_is_the_plain_code(compiler, tmp_path, flags):  # noqa: F811
    # (the same file, written both ways, builds to the same bytes)
    source = tmp_path / 'probe.dewy'
    built = []
    for secret in (False, True):
        source.write_text((probe(secret)) + "\n$runtime_checks\n")
        output = tmp_path / ('secret' if secret else 'plain')
        if 'wasm32' in flags:
            output = output.with_suffix('.html')
        result = run([compiler, 'build', *flags, source, '-o', output])
        assert result.returncode == 0, result.stdout + result.stderr
        if not flags:
            ran = run([output, 'pw'])
            assert ran.returncode == 0 and ran.stdout == 'true\n11\n6\n7\n3.0\n42\n', ran.stdout + ran.stderr
        built.append(output.read_bytes())
    assert len(built[0]) > 1000 and built[0] == built[1]


MAIN = '''Leak:type = type of error & [message:string key:secret<string>]
Hidden:type = type of error & [message:secret<string>]
main = ():>void|Leak|Hidden => {
    if args().length >? 1 return Hidden[secret("pw=hunter2")]
    return Leak["bad login" secret("hunter2")]
}
'''


@pytest.mark.parametrize(('flags', 'leak', 'hidden'), [
    ((), 'error: Leak: bad login', 'error: Hidden'),
    (('-g',), 'error: Leak[message="bad login" key=<redacted>]', 'error: Hidden[message=<redacted>]'),
])
def test_main_error_report_redacts(compiler, tmp_path, flags, leak, hidden):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(MAIN)
    binary = tmp_path / 'main'
    built = run([compiler, 'build', *flags, source, '-o', binary])
    assert built.returncode == 0, built.stdout + built.stderr
    for args, line, code in [((), leak, 1), (('x',), hidden, 2)]:
        ran = run([binary, *args])
        assert ran.returncode == code and line in ran.stderr, ran.stderr
        assert 'hunter2' not in ran.stdout + ran.stderr


@pytest.mark.parametrize(('body', 'requirement'), [
    ('let p:secret<Pos> = k.reveal - 5000', 'refinement failed: `k - 5000 >=? 0`'),
    ('let p:secret<uint8> = k.reveal', 'integer overflow: value does not fit uint8'),
])
def test_runtime_check_report_hides_the_value(compiler, tmp_path, body, requirement):  # noqa: F811
    source = tmp_path / 'check.dewy'
    source.write_text(f'Pos:type = int64<(>=? 0)>\n$runtime_checks\nf = (k:secret<int64>):>void => {{\n'
                      f'    {body}\n    printl(p)\n}}\nf(secret(4242))\n')
    binary = tmp_path / 'check'
    built = run([compiler, 'build', source, '-o', binary])
    assert built.returncode == 0, built.stdout + built.stderr
    ran = run([binary])
    assert ran.returncode == 101 and requirement in ran.stderr, ran.stderr
    assert 'observed' not in ran.stderr and '-758' not in ran.stderr and '4242' not in ran.stderr, ran.stderr


def test_hover_redacts_secret_constants(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'main.dewy'
    text = 'const pin = secret(1234)\nlet key = secret("hunter2")\nmain = () => { printl(pin) printl(key) }\n'
    source.write_text(text)
    client = Client(compiler, tmp_path)
    try:
        diagnostics = client.set_text(source.as_uri(), text, 1)
        assert not [d for d in diagnostics if d['severity'] == 1], diagnostics
        shown = {}
        for name in ('pin', 'key'):
            before = text[:text.rindex(name)]
            position = {'line': before.count('\n'), 'character': len(before.rsplit('\n', 1)[-1])}
            hover = client.request('textDocument/hover', {'textDocument': {'uri': source.as_uri()}, 'position': position})
            shown[name] = hover['contents']['value']
    finally:
        client.close()
    assert 'pin: secret<int> = <redacted>' in shown['pin'] and '1234' not in shown['pin'], shown
    assert 'key: secret<string>' in shown['key'] and 'hunter2' not in shown['key'], shown


def test_gdb_shows_secrets_redacted(compiler, tmp_path):  # noqa: F811
    if not shutil.which('gdb') or not re.match(r'x86_64|amd64', __import__('platform').machine().lower()):
        pytest.skip('gdb on x86-64 required')
    source = tmp_path / 'probe.dewy'
    source.write_text('probe = (pw:secret<string>) => {\n    let n:secret<int64> = 42\n'
                      '    let word = "plain"\n    printl(pw =? word)\n    printl(n.reveal)\n}\n'
                      'main = () => probe(secret("hunter2"))\n')
    binary = tmp_path / 'probe'
    built = run([compiler, 'build', source, '-g', '-o', binary])
    assert built.returncode == 0, built.stdout + built.stderr
    printer = compiler.parent.parent / 'lib/debug/dewy_gdb.py'
    ran = run(['gdb', '--batch', '-nx', '-ex', f'source {printer}', '-ex', f'break {source}:4', '-ex', 'run',
               '-ex', 'info args', '-ex', 'info locals', binary])
    assert 'pw = <redacted>' in ran.stdout and 'n = <redacted>' in ran.stdout, ran.stdout + ran.stderr
    assert 'word = "plain"' in ran.stdout and 'hunter2' not in ran.stdout, ran.stdout
