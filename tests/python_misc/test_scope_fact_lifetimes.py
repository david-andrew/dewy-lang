"""Dead lexical routes must not keep an ever-growing equality graph."""
from pathlib import Path
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.analyze import bounds
from test_scalar_projection import execute

ROOT=Path(__file__).resolve().parents[2]


def test_scoped_snapshots_do_not_accumulate_facts(tmp_path, monkeypatch):
    path=tmp_path/'scoped-facts.dewy'
    path.write_text('work=(value:int64):>int64=>{\n'
        + ''.join(f'{{let saved{i}=value $assert saved{i}=?value}}\n' for i in range(128))
        + 'return value\n}\nmain=():>int64=>work(42)\n')
    original=bounds._BoundsValidator._analyze
    sizes=[]
    def observe(self,node,state,*,validate):
        result=original(self,node,state,validate=validate)
        if self.srcfile.path==path:
            sizes.append(len(result))
        return result
    monkeypatch.setattr(bounds._BoundsValidator,'_analyze',observe)
    execute(tmp_path,'scoped-facts',codegen(SrcFile.from_path(path),debug_locations=False))
    assert sizes and max(sizes)<16


SOURCE='''work=(x:int64):>int64=>{
    let result:int64=0
    loop i in 0..3 {
        {let local=x result=local if i<?2 continue}
        $assert result=?x
    }
    let selected=if x>=?0 {let local=x local} else {let local=x local}
    $assert selected=?x
    return selected
}
main=():>int64=>work(42)
'''


def test_escaping_snapshots_keep_their_own_facts(tmp_path):
    execute(tmp_path,'surviving-facts',codegen(SrcFile(None,SOURCE),debug_locations=False))


def test_native_escaping_scope_facts(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    kernel=(ROOT/'tests/fixtures/native_scope_fact_scaling.dewy').read_text().replace('p"../../dewy/',f'p"{ROOT}/dewy/')
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=[SOURCE,kernel],errors=[])


def test_native_scope_cleanup_kernel(tmp_path):
    execute(tmp_path,'scope-cleanup-kernel',codegen(SrcFile.from_path(ROOT/'tests/fixtures/native_scope_fact_scaling.dewy'),debug_locations=False))
