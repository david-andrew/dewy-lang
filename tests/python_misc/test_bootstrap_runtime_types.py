"""Native runtime-type memoization belongs to a stable lowering state."""
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_runtime_types_are_scoped_and_errors_are_not_cached(tmp_path):
    source = tmp_path / 'runtime-types.dewy'
    source.write_text(f'''
from reporting import SrcFile, Span
import p"{ROOT / 'dewy/bootstrap/semantic/ty.dewy'}" as types
import p"{ROOT / 'dewy/bootstrap/semantic/hir.dewy'}" as hir
import p"{ROOT / 'dewy/bootstrap/backend/udewy/lower.dewy'}" as lower
import p"{ROOT / 'dewy/bootstrap/backend/udewy/emit.dewy'}" as emit
main=():>int64=>{{
    let word_types:types.Table=types.Table[]
    let word=types.primitive('uint32' @word_types)
    let string_types:types.Table=types.Table[]
    let text=types.primitive('string' @string_types)
    $runtime_assert word =? text
    let first=lower.State[emit.Input[[] word_types] SrcFile['first' ''] type_nodes=word_types]
    let next=lower.State[emit.Input[[] string_types] SrcFile['next' ''] type_nodes=string_types]
    let node=hir.Void[Span[0 1] word]
    let a=lower.runtime_type(word node @first)
    let b=lower.runtime_type(text node @next)
    $runtime_assert types.is_primitive(types.node_at(first.type_nodes a) 'uint32')
    $runtime_assert types.is_primitive(types.node_at(next.type_nodes b) 'int64')
    # Appending descriptions must preserve earlier answers. A nested record
    # validates each field and retains the same concrete representation.
    let array=types.array_type(text none @next.type_nodes)
    let record=types.object_type([types.ObjectField['items' array]] none false [] [] @next.type_nodes)
    $runtime_assert lower.runtime_type(record node @next) =? b
    $runtime_assert lower.runtime_type(text node @next) =? b
    $runtime_assert lower.cell_members(text @next) is? none
    let optional=types.union([text types.primitive('none' @next.type_nodes)] @next.type_nodes)
    let members=lower.cell_members(optional @next)
    $runtime_assert members isnt? none and members.length =? 2
    # A caller's modification of a returned member list is a value copy;
    # it cannot change the cached representation of this union.
    members.clear
    let again=lower.cell_members(optional @next)
    $runtime_assert again isnt? none and again.length =? 2
    $runtime_assert lower.cell_members(text @next) is? none
    let invalid=types.primitive('no_runtime_representation' @next.type_nodes)
    lower.runtime_type(invalid node @next);
    $runtime_assert next.problem isnt? none
    next.problem=none
    lower.runtime_type(invalid hir.Void[Span[5 6] word] @next);
    $runtime_assert next.problem isnt? none
    let problem=next.problem
    $runtime_assert problem isnt? none and problem.pointers.length >? 0
    $runtime_assert problem.pointers[0].span.start =? 5
    return 42
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    for target in ('x86_64', 'c'):
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, timeout=15)
        assert result.returncode == 42, result.stderr.decode()
