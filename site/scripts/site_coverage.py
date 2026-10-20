"""Generate target-scoped reference coverage from fresh acceptance results."""
from __future__ import annotations
import html
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools import cases


def collect(compiler: Path, dist: Path, scratch: Path) -> dict:
    mapping = json.loads((ROOT/'site/coverage-map.json').read_text())
    output = dist/'coverage'; output.mkdir()
    subprocess.run([sys.executable, '-m', 'tools.ladder', '--compiler', str(compiler),
                    '-n', '1', '--json', str(output/'ladder.json')], cwd=ROOT, check=True)
    ladder = json.loads((output/'ladder.json').read_text())
    runner = cases.Runner(compiler, scratch, cases.clean_environment())
    goldens = {}
    for name in sorted({name for row in mapping for name in row['golden']}):
        case = cases.parse(ROOT/'tests/cases'/f'{name}.dewy')
        if 'native-release' not in case.modes:
            raise ValueError(f'{name}: metadata requests an unsupported golden target')
        result, = runner.single(case, 'native-release')
        goldens[name] = {'ok':result.ok, 'error':result.message, 'target':'native-release'}
        if not result.ok: raise ValueError(f'{name}: {result.message}')
    design = {r['program']:r for r in ladder['results'] if r['version']=='design'}
    for row in mapping:
        for name in row['ladder']:
            if name not in design: raise ValueError(f'unknown ladder ID: {name}')
        for test in row['pytest']:
            path, function = test.split('::')
            if f'def {function}(' not in (ROOT/path).read_text():
                raise ValueError(f'unknown pytest ID: {test}')
        row['status'] = 'partial' if row['ladder'] or row['golden'] else ('not measured' if row['pytest'] else 'design only')
        row['target'] = 'native-release'
        row['pytest_status'] = 'not measured'
    return {'sections':mapping, 'golden':goldens, 'ladder':ladder}


def render(data: dict, revision: str) -> str:
    rows = []
    base = f'https://github.com/david-andrew/dewy-lang/blob/{revision}/'
    for row in data['sections']:
        name = row['page']; label = name.replace('-', ' ').title()
        refs = []
        for kind, values in [('ladder',row['ladder']),('golden',row['golden']),('pytest',row['pytest'])]:
            for value in values:
                path = f'tests/ladder/{value}/design.dewy' if kind=='ladder' else f'tests/cases/{value}.dewy' if kind=='golden' else value.split('::')[0]
                if kind == 'pytest': suffix = ' (not measured)'
                elif kind == 'golden': suffix = ' (pass · native-release)'
                else:
                    result = next(r for r in data['ladder']['results'] if r['program']==value and r['version']=='design')
                    suffix = ' (design pass · native-release)' if result['ok'] else ' (design FAIL: '+html.escape(result['error'])+')'

                refs.append(f'<a href="{base}{path}">{html.escape(value)}</a>{suffix}')
        target='/reference/'+name+'.html'+('#'+row['section'] if row['section'] else '')
        rows.append(f'<tr id="ref-{name}"><th scope="row"><a href="{target}">{label}</a></th><td>{row["status"]}</td><td>{"<br>".join(refs) or "No executable claim"}</td></tr>')
    return '<div class="coverage-scroll"><table><caption>Reference associations · native release only; each row covers the named section</caption><thead><tr><th>Section</th><th>Coverage</th><th>Related test IDs</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'
