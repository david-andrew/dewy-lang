"""Indexed runtime-report geometry retains grapheme and end-of-file semantics."""
import json
from pathlib import Path
import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
CASES = [
    ('', [0], [0]),
    ('\n', [0, 1], [0, 1]),
    ('\r\n', [0, 1], [0, 1]),
    ('\r', [0], [1]),
    ('one\n\ntwo', [0, 4, 5], [3, 4, 8]),
    ('a\u0301\r\n👨\u200d👩\u200d👧\u200d👦\nZ', [0, 2, 4], [1, 3, 5]),
    ('a\u2028b\u2029c', [0], [5]),
]


def geometry_source():
    cases = []
    for case, (text, starts, ends) in enumerate(CASES):
        literal = json.dumps(text, ensure_ascii=False)
        cases.append(f"if not compare({literal} [{' '.join(map(str, starts))}] [{' '.join(map(str, ends))}]) return {10 + case}")
    return f'''from reporting import SrcFile
import p"{ROOT / 'dewy/bootstrap/semantic/source_lines.dewy'}" as lines
compare=(body:string starts:array<addr> ends:array<addr>):>bool=>{{
    let source=SrcFile['test' body 17]
    let index=lines.build(body)
    if index.starts.length not=? starts.length or index.ends.length not=? ends.length return false
    loop i in 0.. and i <? starts.length and i <? index.starts.length {{
        if index.starts[i] not=? starts[i] return false
    }}
    loop i in 0.. and i <? ends.length and i <? index.ends.length {{
        if index.ends[i] not=? ends[i] return false
    }}
    $runtime_assert body.length <? 100
    loop offset in 0..102 {{
        if offset >? body.length+2 break
        let located=lines.locate(index offset)
        if located.row not=? source.line_of(offset) return false
        if located.begin not=? source.line_start(located.row) return false
        if located.limit not=? source.line_end(located.row) return false
    }}
    return true
}}
main=():>int64=>{{
    {chr(10).join(cases)}
    let rows:array<string>=[]
    loop i in 0..1999 {{rows.push('abcdef\n')}}
    let body=rows.join
    let index=lines.build(body)
    let before:int64=_arena_allocated_bytes
    loop i in 0..3999 {{
        let located=lines.locate(index body.length)
        if located.row not=? 2000 or located.begin not=? body.length or located.limit not=? body.length return 2
    }}
    # Source indexing must not be rebuilt, or copied in proportion to source
    # size, for each report. Cumulative payload allocation catches both costs.
    if _arena_allocated_bytes-before >=? 10000000 return 3
    return 42
}}
'''


def test_indexed_geometry_matches_source_views(tmp_path):
    source = tmp_path / 'geometry.dewy'
    source.write_text(geometry_source())
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                            text=True, timeout=10, check=False)
    assert result.returncode == 42, result.stderr


def test_runtime_report_materialization_keeps_source_geometry(tmp_path):
    source = ROOT / 'tests/fixtures/native_report_geometry.dewy'
    output = tmp_path / 'reports.udewy'
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                            text=True, timeout=10, check=False)
    assert result.returncode == 42, result.stderr
