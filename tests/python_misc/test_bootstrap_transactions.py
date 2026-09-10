"""Nested semantic alternatives restore rewrites as well as appended arenas."""
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_nested_checkpoints(tmp_path):
    source = tmp_path / 'transactions.dewy'
    source.write_text(f'''
from reporting import Span
import p"{ROOT / 'dewy/bootstrap/semantic/context.dewy'}" as contexts
import p"{ROOT / 'dewy/bootstrap/semantic/ty.dewy'}" as types
import p"{ROOT / 'dewy/bootstrap/semantic/hir.dewy'}" as hir
main = ():>int64 => {{
    let session=contexts.Session[]
    let word=types.primitive('int64' @session.types)
    let original=hir.append_node(@session.hir hir.Integer[Span[0 1] word '0d' 1])
    let before=contexts.checkpoint(session)
    contexts.replace_hir(original hir.Integer[Span[0 1] word '0d' 2] @session)
    let added=hir.append_node(@session.hir hir.Integer[Span[0 1] word '0d' 3])
    let inner=contexts.checkpoint(session)
    contexts.replace_hir(original hir.Integer[Span[0 1] word '0d' 4] @session)
    contexts.replace_hir(added hir.Integer[Span[0 1] word '0d' 5] @session)
    let discarded=types.primitive('string' @session.types)
    session.syntax_refs.push(contexts.SyntaxRef[0 0 0])
    session.named_refs[12]=added
    contexts.restore(inner @session)
    let restored=hir.node_at(session.hir original)
    let suffix=hir.node_at(session.hir added)
    $runtime_assert restored is? hir.Integer and restored.value =? 2
    $runtime_assert suffix is? hir.Integer and suffix.value =? 3
    $runtime_assert session.syntax_refs.length =? 0 and 12 not in? session.named_refs
    contexts.restore(before @session)
    let first=hir.node_at(session.hir original)
    $runtime_assert first is? hir.Integer and first.value =? 1
    $runtime_assert session.hir.length =? 1 and session.hir_edits.length =? 0
    # Replaying a candidate reuses ids; its discarded type and HIR suffix
    # cannot affect interning or the next candidate's binding references.
    $runtime_assert types.primitive('bool' @session.types) =? discarded
    $runtime_assert hir.append_node(@session.hir hir.Integer[Span[0 1] word '0d' 6]) =? added
    contexts.replace_hir(original hir.Integer[Span[0 1] word '0d' 7] @session)
    contexts.restore(before @session)
    let final=hir.node_at(session.hir original)
    $runtime_assert final is? hir.Integer and final.value =? 1
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                            text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
