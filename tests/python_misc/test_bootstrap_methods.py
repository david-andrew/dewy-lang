"""Native record methods retain scopes, receivers, and hidden signatures."""
import test_bootstrap_check as source_values

CASES = [
    'T:type=[x:int64 get=()=>x]\nT[7].get',
    'T:type=[x:int64 clear=()=>{x=0} reset=()=>{clear}]\nlet t=T[7]\nt.reset\nt.x',
    'T:type=[x:int64 get=():>int64=>x]\nT[7].get()',
    'T:type=[x:int64 plus=(n:int64):>int64=>x+n]\nT[7].plus(2)',
    'T:type=[x:int64 plus=(n:int64=2):>int64=>x+n]\nT[7].plus()',
    'T:type=[x:int64 plus=(n:int64):>int64=>x+n]\nT[7].plus(n=2)',
    'T:type=[x:int64 get=(self:int64)=>self+x]\nT[7].get(2)',
    'T:type=[x:int64 get=(x:int64)=>x]\nT.get(2)',
    'T:type=[x:int64 get=()=>{let x:int64=8 x}]\nT.get',
    'T:type=[x:int64 set=(n:int64)=>{x=n}]\nlet t=T[7]\nt.set(8)\nt.x',
    'T:type=[x:int64 grow=(n:int64)=>{x+=n}]\nlet t=T[7]\nt.grow(8)\nt.x',
    'T:type=const[x:int64 copy=():>[x:int64]=>[x=x]]\nT[7].copy.x',
    'T:type=const[x:int64 copy=():>[x:int64]=>[x:int64=x]]\nT[7].copy.x',
    'T:type=[value=()=>7]\nT.value',
    'T:type=[value=()=>7]\nT[].value',
    'T:type=[value=()=>7 twice=()=>value+value]\nT.twice',
    'T:type=[twice=()=>value+value value=()=>7]\nT.twice',
    'T:type=[x:int64 get=()=>x twice=()=>get+get]\nT[7].twice',
    'T:type=[x:int64 twice=()=>get+get get=()=>x]\nT[7].twice',
    'T:type=[count=()=>7 build=():>[count:int64]=>[count=count]]\nT.build.count',
    'let n=3\nT:type=[x:int64 get=(by:int64=n)=>x+by]\nT[7].get()',
    'T:type=[x:int64 get=()=>{let f=(n:int64)=>n+x f(2)}]\nT[7].get',
    'T:type=[x:int64 move=(n:int64):>T=>T[x+n]]\nT[7].move(2).x',
    'Root=$abstract type of [x:int64 get=()=>x]\nChild=type of Root\nChild[7].get',
    'Root=$abstract type of [x:int64 get=()=>x]\nChild=type of Root & [y:int64=2]\nChild[7].get',
]
ERRORS = [
    'T:type=[x:int64 get=()=>x]\nT.get',
    'T:type=[x:int64 set=(n:int64)=>{x=n}]\nT[7].set(8)',
    'T:type=[x:int64 set=(n:int64)=>{x=n}]\nconst t=T[7]\nt.set(8)',
    'T:type=const[x:int64 set=(n:int64)=>{x=n}]',
    'T:type=const[x:int64 set=(n:int64)=>{x+=n}]',
    'T:type=[x:int64 get=()=>self]',
    'T:type=[x:int64 get=(n:int64)=>x+n]\nT[7].get',
    'T:type=[x:int64 get=()=>x]\nT[7].get(1)',
    'T:type=[x:int64 get=()=>x]\nT[7].missing',
    'T:type=[f=()=>f()]',
    'T:type=[x:int64 get=(n:int64=2)=>x+n]\nT[7].get',
    'T:type=[data:dict<string int64> clear=()=>{data.clear} reset=()=>{clear}]\nlet t=T[["a"->1]]\nif "a" in? t.data {t.clear let x:int64=t.data["a"]}',
]


def test_native_record_methods(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERRORS)
    source_values.test_native_source_values(tmp_path)
