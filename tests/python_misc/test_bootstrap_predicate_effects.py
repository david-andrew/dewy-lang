"""Predicate input lifetimes use the same binding roots in both compilers."""

import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import hir
from dewy.semantic.analyze.predicate_effects import mutated_bindings, read_bindings
from tests.python_misc.test_bootstrap_effects import effect_program, emit_hir
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point
from driver_artifacts import isolated_codegen

ROOT = Path(__file__).resolve().parents[2]


def test_native_predicate_dependencies_match_hosted(tmp_path):
    root = effect_program()
    lines, _, names = emit_hir(root, with_names=True)
    rows = []
    seen = set()
    examined = []
    pending = [root]
    while pending:
        node = pending.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        examined.append(node)
        pending.extend(hir.children(node))
    summaries = {id(node): {700, 701} for node in examined if isinstance(node, hir.FunctionCall)}
    for node in examined:
        reads = ' '.join(map(str, sorted(read_bindings(node))))
        writes = ' '.join(map(str, sorted(mutated_bindings(node))))
        summarized = ' '.join(map(str, sorted(mutated_bindings(node, call_writes=summaries))))
        rows.append(f'[{names[id(node)]} set[{reads}] set[{writes}] set[{summarized}]]')
    summary_entries = ' '.join(f'{names[key]} -> set[700 701]' for key in summaries)
    source = tmp_path / 'predicate_effects.dewy'
    source.write_text(f'''from reporting import Span
import p"{ROOT / 'dewy/bootstrap/semantic/ty.dewy'}" as types
import p"{ROOT / 'dewy/bootstrap/semantic/hir.dewy'}" as hir
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/predicate_effects.dewy'}" as effects
Case:type = const [node:addr reads:set<addr> writes:set<addr> summarized:set<addr>]
main = ():>int64 => {{
    let span=Span[0 0]
    let arena:types.Table=types.Table[]
    let scalar=types.primitive('any' @arena)
    let callable=types.function_type([] [] none scalar [] @arena)
    let nodes:array<hir.AST>=[]
{chr(10).join(lines)}
    let summaries:dict<addr set<addr>>=[{summary_entries}]
    let cases:array<Case>=[{' '.join(rows)}]
    loop case in cases {{
        let reads=effects.read_bindings(case.node nodes)
        let writes=effects.mutated_bindings(case.node nodes)
        $runtime_assert reads.length =? case.reads.length
        $runtime_assert writes.length =? case.writes.length
        loop binding in reads {{ $runtime_assert binding in? case.reads }}
        loop binding in writes {{ $runtime_assert binding in? case.writes }}
        let summarized=effects.mutated_bindings(case.node nodes call_writes=summaries)
        $runtime_assert summarized.length =? case.summarized.length
        loop binding in summarized {{ $runtime_assert binding in? case.summarized }}
        summarized.push(999)
    }}
    # Reading a call summary must not lend writable storage to the result.
    loop summary in summaries.values {{
        $runtime_assert summary.length =? 2 and 999 not in? summary
    }}
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    isolated_codegen(output, source)
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stderr
