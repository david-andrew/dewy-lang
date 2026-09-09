"""Predicate input lifetimes use the same binding roots in both compilers."""

import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.analyze.effects import _iter_children
from dewy.semantic.analyze.predicate_effects import mutated_bindings, read_bindings
from tests.python_misc.test_bootstrap_effects import effect_program, emit_hir
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_predicate_dependencies_match_hosted(tmp_path):
    root = effect_program()
    lines, _, names = emit_hir(root, with_names=True)
    rows = []
    seen = set()
    pending = [root]
    while pending:
        node = pending.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        reads = ' '.join(map(str, sorted(read_bindings(node))))
        writes = ' '.join(map(str, sorted(mutated_bindings(node))))
        rows.append(f'[{names[id(node)]} set[{reads}] set[{writes}]]')
        pending.extend(_iter_children(node))
    source = tmp_path / 'predicate_effects.dewy'
    source.write_text(f'''from reporting import Span
import p"{ROOT / 'dewy/bootstrap/semantic/ty.dewy'}" as types
import p"{ROOT / 'dewy/bootstrap/semantic/hir.dewy'}" as hir
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/predicate_effects.dewy'}" as effects
Case:type = const [node:addr reads:set<addr> writes:set<addr>]
main = ():>int64 => {{
    let span=Span[0 0]
    let arena:array<types.Type>=[]
    let scalar=types.primitive('any' @arena)
    let callable=types.function_type([] [] none scalar [] @arena)
    let nodes:array<hir.AST>=[]
{chr(10).join(lines)}
    let cases:array<Case>=[{' '.join(rows)}]
    loop case in cases {{
        let reads=effects.read_bindings(case.node nodes)
        let writes=effects.mutated_bindings(case.node nodes)
        $runtime_assert reads.length =? case.reads.length
        $runtime_assert writes.length =? case.writes.length
        loop binding in reads {{ $runtime_assert binding in? case.reads }}
        loop binding in writes {{ $runtime_assert binding in? case.writes }}
    }}
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stderr
