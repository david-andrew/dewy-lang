"""Qualifying a static call must preserve an object literal's field names."""
import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


def test_static_methods_build_records_with_names_matching_their_methods(tmp_path):
    source = tmp_path / 'keys.dewy'
    source.write_text('''T:type=[
    count=():>int64=>7
    build=():>[count:int64]=>[count=count]
    nested=():>[part:[count:int64]]=>[part=[count=count]]
    typed=():>[count:int64]=>[count:int64=count]
]
C:type=const [count:int64 copy=():>[count:int64]=>[count:int64=count]]
let main=():>int64=>{
    printl(T.build.count)
    printl(T.nested.part.count)
    printl(T.typed.count)
    printl(C[7].copy.count)
    return 0
}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout == '7\n7\n7\n7\n'
