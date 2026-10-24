"""A lazy census belongs to a stable input, and every use must initialize it."""
import subprocess

import pytest

from tests.support import compiler


@pytest.mark.parametrize('release', [False, True])
def test_repeated_census_paths_and_changed_inputs(compiler, tmp_path, release):
    source = tmp_path / 'census.dewy'
    source.write_text(('''
repeated=(xs:array<int64> first:bool):>array<int64>=>{
    let out:array<int64>=[]
    if first out=xs .* xs .- xs
    loop i in [0..3) out=xs .* xs .- xs
    return out
}
changed=(value:int64):>array<int64>=>{
    let xs:array<int64>=[1 2]
    let out:array<int64>=[]
    loop i in [0..2) {
        out=xs .* xs .- xs
        xs=[value value]
    }
    return out
}
main=(args:array<string>)=>{
    let value=int64(to_int(args[1]) ?? 0)
    let xs:array<int64>=[value value]
    if args[2]=?"changed" printl(changed(value))
    else printl(repeated(xs args[2]=?"first"))
}
''') + "\n$runtime_checks\n")
    binaries = []
    for debug in [False, True]:
        binary = tmp_path / ('scalar' if debug else 'census')
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else []),
                                *(['-g'] if debug else [])], capture_output=True, text=True)
        assert built.returncode == 0, built.stderr
        binaries.append(binary)
    for value in [0, -7, 2**30, 2**32, -2**63]:
        for path in ['first', 'later', 'changed']:
            runs = [subprocess.run([b, str(value), path], capture_output=True, text=True)
                    for b in binaries]
            expected = value * value - value
            for run in runs:
                assert (run.returncode == 0) == (-2**63 <= expected < 2**63), (value, path, run.stderr)
            assert runs[0].stdout == runs[1].stdout
