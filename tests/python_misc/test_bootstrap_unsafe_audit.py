"""Native audit collection retains nested scopes and escaped source text."""
import json
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, Span
from dewy.semantic import hir, ty, unsafe_audit
from test_bootstrap_effects import emit_hir
from test_bootstrap_initialization import type_builder
from test_scalar_projection import execute

ROOT=Path(__file__).resolve().parents[2]


def test_native_audit_collection_matches_hosted(tmp_path):
    loc=Span(0,0)
    source=SrcFile(Path('audit-input.dewy'),'x')
    signature=ty.FunctionType([],[],None,'void')
    def assumption(message):
        return hir.Assert(loc,'void',hir.Bool(loc,'bool',True),'true',message,unsafe=True)
    def declare(name,body):
        function=hir.FunctionLiteral(loc,signature,[],[],None,'void',hir.Block(loc,'void',body,True))
        return hir.Declare(loc,'void','let',name,signature,function)
    check=hir.Assert(loc,'void',hir.Bool(loc,'bool',True),'checked')
    nested=declare('nested',[assumption('nested\r\n"quote"\\雪'),check])
    outer=declare('outer',[assumption('first'),nested,assumption('second'),check])
    anonymous=hir.FunctionLiteral(loc,signature,[],[],None,'void',hir.Block(loc,'void',[assumption('anonymous'),check],True))
    root=hir.Block(loc,'void',[outer,anonymous,assumption('module')],False)
    expected=json.loads(unsafe_audit.render(unsafe_audit.collect(root,source)))
    type_lines=[]
    lines,root_id=emit_hir(root,type_value=type_builder(type_lines))
    path=tmp_path/'audit.dewy'
    path.write_text(f'''from reporting import Span, SrcFile
import p"{ROOT / 'dewy/bootstrap/semantic/hir.dewy'}" as hir
import p"{ROOT / 'dewy/bootstrap/semantic/ty.dewy'}" as types
import p"{ROOT / 'dewy/bootstrap/semantic/context.dewy'}" as contexts
import p"{ROOT / 'dewy/bootstrap/semantic/unsafe_audit.dewy'}" as audit
main=():>int64=>{{
    let span=Span[0 0]
    let nodes:array<hir.AST>=[]
    let type_nodes=types.Table[]
{chr(10).join(type_lines+lines)}
    let session=contexts.Session[hir=nodes types=type_nodes]
    session.unsafe_assertions.push({root_id})
    let source=SrcFile['audit-input.dewy' 'x']
    let entries=audit.collect({root_id} source session)
    print(audit.render(entries))
    return 42
}}
''')
    for result in execute(tmp_path,'audit',codegen(SrcFile.from_path(path),debug_locations=False)):
        assert json.loads(result.stdout)==expected
