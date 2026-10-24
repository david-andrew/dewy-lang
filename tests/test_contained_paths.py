"""Untrusted input reaching the file system: a path built from text that came from outside
(arguments, environment, standard input, file contents, the network) warns where a file
operation gets it, unless `contains` or `confine` stood in between; hardcoded paths never warn.
Passing an unproven path where a SafePath is declared is an error; the editor fixes both with
`root.confine(p) or_throw`. (Runtime behavior and the errors: tests/cases/contained.)"""
import os
import re
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_core_editor import Client

UNTRUSTED = 'holds untrusted input'
UNPROVEN = 'is not proven to stay inside its base'

# David's example: the read after the checks warns, the validated uses do not.
HANDLER = '''let root=p"/srv/site/static"
Request:type=[name:string]
Response:type=[body:string]
serve_file=(f:SafePath):>Response | FileError=>{
    return Response["{f}"]
}
handle=(req:Request):>void | PathEscape | FileError=>{
    let f=p"{root}/{req.name}"
    serve_file(root.confine(f) or_throw) or_throw;
    if root.contains(f) { serve_file(f) or_throw; }
    let n=f.read_text   # warning
    printl(n is? error)
}
main=():>void | PathEscape | FileError=>{
    let line=read_line()
    let name=if line is? string line else "index.html"
    handle(Request[name]) or_throw
}
'''

# Each source, through locals, fields, loops, helpers and lambdas, to a file operation.
SOURCES = '''let base=p"/srv/data"
Job:type=[name:string id:int64]
path_for=(name:string):>Path=>p"{base}/{name}"
main=():>void=>{
    let argv=args()
    loop a in argv { printl(p"{base}/{a}".exists) }
    let home=env("HOME") ?? "nobody"
    printl(p"{base}/{home}".is_dir)
    let listed=p"{base}/list.txt".read_text
    if listed is? string { printl(read_text("{base}/{listed}") is? error) }
    let job=Job[argv[0] 1]
    printl(path_for(job.name).size is? error)
    let paths=argv.map(x => p"{base}/{x}")
    loop q in paths { printl(q.exists) }
}
'''

# Nothing here warns: hardcoded paths, a helper given trusted text, untrusted text that only
# numbers come from, a record whose other field is untrusted, validated and guarded paths.
QUIET = '''let base=p"/srv/data"
Job:type=[name:string root:string]
path_for=(name:string):>Path=>p"{base}/{name}"
main=():>void=>{
    printl(p"/etc/hosts".exists)
    printl(p"{base}/fixed.txt".exists)
    printl(path_for("trusted.txt").exists)
    let argv=args()
    let count=argv.length
    printl(p"{base}/{count}.txt".exists)
    let job=Job[argv[0] "/srv/jobs"]
    printl(p(job.root).is_dir)
    let f=p"{base}/{argv[0]}"
    if base.contains(f) { printl(f.exists) }
    let g=base.confine(f)
    if g is? Path { printl(g.exists) }
    let tried=path_for(argv[0])
    printl(tried.parent.name)
}
'''


def diagnostics_of(compiler, path, word):  # noqa: F811
    checked = subprocess.run([compiler, 'check', path], capture_output=True, text=True,
                             timeout=60, check=False)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    return [line for line in checked.stderr.splitlines() if word in line]


def line_of(found):
    return int(re.search(r'\.dewy:(\d+):\d+: ', found).group(1))


def lines_of(found):
    return sorted(line_of(line) for line in found)


def test_handler_warns_only_after_its_checks(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(HANDLER)
    found = diagnostics_of(compiler, source, UNTRUSTED)
    assert lines_of(found) == [11], found
    assert '`f` holds untrusted input (`read_line` on line 15)' in found[0], found
    assert 'validate it, `root.confine(f) or_throw`, or test it first, `if root.contains(f) {...}`' in found[0]
    run = subprocess.run([compiler, 'run', source], input='../../etc/passwd\n', capture_output=True,
                         text=True, timeout=60, check=False)
    assert run.returncode != 0 and 'PathEscape' in run.stderr, run.stdout + run.stderr


def test_each_source_reaches_its_sink(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(SOURCES)
    found = diagnostics_of(compiler, source, UNTRUSTED)
    origins = {line_of(line): line for line in found}
    assert sorted(origins) == [6, 8, 10, 12, 14], found
    assert '`args` on line 5' in origins[6]
    assert '`env` on line 7' in origins[8]
    assert '`read_text` on line 9' in origins[10]
    # (the helper's result holds its argument: the call is where the warning goes)
    assert '`args` on line 5' in origins[12]
    assert '`q` holds untrusted input' in origins[14]


def test_trusted_and_validated_paths_are_quiet(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(QUIET)
    assert diagnostics_of(compiler, source, UNTRUSTED) == []


def test_editor_validates_the_path(tmp_path):
    value = os.environ.get('DEWY_CORE_COMPILER')
    if not value:
        pytest.skip('set DEWY_CORE_COMPILER for the editor checks')
    source = tmp_path / 'main.dewy'
    source.write_text('main=():>void=>exit(0)')
    client = Client(Path(value).resolve(strict=True), tmp_path)
    try:
        diagnostics = client.set_text(source.as_uri(), HANDLER, 1)
        warnings = [d for d in diagnostics if d['severity'] == 2 and UNTRUSTED in d['message']]
        assert len(warnings) == 1, diagnostics
        assert warnings[0]['range']['start'] == {'line': 10, 'character': 10}, warnings
        actions = client.request('textDocument/codeAction', {
            'textDocument': {'uri': source.as_uri()}, 'range': warnings[0]['range'],
            'context': {'diagnostics': warnings},
        })
        assert len(actions) == 1, actions
        edits = actions[0]['edit']['changes'][source.as_uri()]
        start, end = {'line': 10, 'character': 10}, {'line': 10, 'character': 11}
        assert edits == [{'range': {'start': start, 'end': end},
                          'newText': '(root.confine(f) or_throw)'}], edits
        fixed = HANDLER.replace('let n=f.read_text', 'let n=(root.confine(f) or_throw).read_text')
        diagnostics = client.set_text(source.as_uri(), fixed, 2)
        assert not [d for d in diagnostics if UNTRUSTED in d['message'] or d['severity'] == 1], diagnostics

        unproven = HANDLER.replace('serve_file(root.confine(f) or_throw) or_throw', 'serve_file(f) or_throw')
        diagnostics = client.set_text(source.as_uri(), unproven, 3)
        errors = [d for d in diagnostics if d['severity'] == 1 and UNPROVEN in d['message']]
        assert len(errors) == 1, diagnostics
        actions = client.request('textDocument/codeAction', {
            'textDocument': {'uri': source.as_uri()}, 'range': errors[0]['range'],
            'context': {'diagnostics': errors},
        })
        assert len(actions) == 1, actions
        edits = actions[0]['edit']['changes'][source.as_uri()]
        assert [e['newText'] for e in edits] == ['root.confine(f) or_throw'], edits
    finally:
        client.close()
