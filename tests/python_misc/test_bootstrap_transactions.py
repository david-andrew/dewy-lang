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
import p"{ROOT / 'dewy/bootstrap/semantic/subtyping.dewy'}" as subtyping
import p"{ROOT / 'dewy/bootstrap/semantic/hir.dewy'}" as hir
main = ():>int64 => {{
    let session=contexts.Session[]
    let word=types.primitive('int64' @session.types)
    let original=hir.append_node(@session.hir hir.Integer[Span[0 1] word '0d' 1])
    session.read_states.push(contexts.ReadState[types=[1 -> word]])
    session.retained_read_states.push(0)
    subtyping.add_link(@session.links subtyping.Link['Before' 'int'])
    let before=contexts.checkpoint(session)
    subtyping.add_link(@session.links subtyping.Link['Outer' 'Before'])
    contexts.replace_hir(original hir.Integer[Span[0 1] word '0d' 2] @session)
    let added=hir.append_node(@session.hir hir.Integer[Span[0 1] word '0d' 3])
    let inner=contexts.checkpoint(session)
    subtyping.add_link(@session.links subtyping.Link['Before' 'bool'])
    contexts.replace_hir(original hir.Integer[Span[0 1] word '0d' 4] @session)
    contexts.replace_hir(added hir.Integer[Span[0 1] word '0d' 5] @session)
    let discarded=types.primitive('string' @session.types)
    session.syntax_refs.push(contexts.SyntaxRef[0 0 0])
    session.named_refs[12]=added
    session.read_states.push(contexts.ReadState[types=[2 -> word]])
    session.retained_read_states.push(1)
    contexts.restore(inner @session)
    $runtime_assert subtyping.nominal_subtype('Outer' 'int' session.links)
    $runtime_assert not subtyping.nominal_subtype('Before' 'bool' session.links)
    $runtime_assert session.read_states.length =? 1
    $runtime_assert 0 in? session.retained_read_states and 1 not in? session.retained_read_states
    let restored=hir.node_at(session.hir original)
    let suffix=hir.node_at(session.hir added)
    $runtime_assert restored is? hir.Integer and restored.value =? 2
    $runtime_assert suffix is? hir.Integer and suffix.value =? 3
    $runtime_assert session.syntax_refs.length =? 0 and 12 not in? session.named_refs
    contexts.restore(before @session)
    $runtime_assert not subtyping.nominal_subtype('Outer' 'int' session.links)
    $runtime_assert subtyping.nominal_subtype('Before' 'int' session.links)
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
    # Finished branches release facts and trailing slots. Captured generic
    # environments keep stable indices even when earlier slots are cleared.
    session.read_states.push(contexts.ReadState[types=[2 -> word]])
    session.read_states.push(contexts.ReadState[types=[3 -> word]])
    session.retained_read_states.push(2)
    session.read_states.push(contexts.ReadState[types=[4 -> word]])
    contexts.release_read_states(1 @session)
    $runtime_assert session.read_states.length =? 3
    $runtime_assert session.read_states[1].types.length =? 0
    $runtime_assert 3 in? session.read_states[2].types
    $runtime_assert 1 in? session.read_states[0].types
    # Interned syntax identities distinguish both source and lexical scope.
    # Discarded suffix entries must not survive rollback or overwrite the
    # next reference that reuses their arena position.
    let origin=contexts.Context[0 0]
    let first_ref=contexts.syntax_ref(12 origin @session)
    let scoped=contexts.syntax_ref(12 contexts.Context[0 1] @session)
    $runtime_assert first_ref =? 0 and scoped =? 1
    let saved=contexts.checkpoint(session)
    let rejected=contexts.syntax_ref(12 contexts.Context[1 0] @session)
    $runtime_assert rejected =? 2
    contexts.restore(saved @session)
    $runtime_assert contexts.syntax_ref(12 origin @session) =? first_ref
    $runtime_assert contexts.syntax_ref(13 origin @session) =? rejected
    $runtime_assert contexts.syntax_ref(12 contexts.Context[1 0] @session) =? 3
    # A preloaded arena is indexed lazily and retains first-match behavior.
    let loaded=contexts.Session[syntax_refs=[contexts.SyntaxRef[4 5 6] contexts.SyntaxRef[4 5 6]]]
    $runtime_assert contexts.syntax_ref(5 contexts.Context[4 6] @loaded) =? 0
    $runtime_assert contexts.syntax_ref(6 contexts.Context[4 6] @loaded) =? 2
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                            text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
