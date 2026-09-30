"""Library boundary cases with independent expected results (September 29
audit follow-up, item 7). Paired compiler agreement cannot validate an
algorithm both compilers share; these expectations come from exact
arithmetic or the operating system, not from either compiler."""
import resource
import subprocess
from fractions import Fraction
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point
from test_scalar_projection import execute

MINIMUM = -2**63


def fixed_quotient(numerator: int, denominator: int) -> int:
    """Q32.32 division rounded half away from zero, as the library documents."""
    exact = Fraction(numerator * 2**32, denominator)
    magnitude = abs(exact)
    rounded = int(magnitude) + (1 if magnitude - int(magnitude) >= Fraction(1, 2) else 0)
    return rounded if exact >= 0 else -rounded


def fixed_division_source() -> str:
    checks = []
    for index, raw in enumerate([MINIMUM, 2**40, -2**40, 3 * 2**30, 1, -1, 2**63 - 1]):
        checks.append(f'    let a{index}:fixed=[raw=({raw})]\n'
                      f'    if (a{index}/b).raw not=? ({fixed_quotient(raw, MINIMUM)}) return {index + 1}')
    return 'main=():>int64=>{\n    let b:fixed=[raw=(' + str(MINIMUM) + ')]\n    if b.raw =? 0 return 99\n' + '\n'.join(checks) + '\n    return 42\n}\n'


# A NUL would end the kernel's reading of a path early and name another file.
NUL_PATH = '''main=():>int64=>{
    if not file_exists("/etc/passwd") return 1
    if file_exists("/etc/passwd\x00ignored") return 2
    let text=read_text("/etc/passwd\x00ignored")
    if text is? string return 3
    return 42
}
'''
CASES = [fixed_division_source(), NUL_PATH]


def test_fixed_minimum_division(tmp_path):
    execute(tmp_path, 'fixed-minimum', codegen(SrcFile(None, CASES[0]), debug_locations=False))


def test_nul_path_is_rejected(tmp_path):
    execute(tmp_path, 'nul-path', codegen(SrcFile(None, CASES[1]), debug_locations=False))


def test_native_library_boundaries(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[])


def test_capture_releases_its_first_pipe_when_the_second_fails(tmp_path):
    # With five descriptors, 0-2 are open and the first pipe takes 3 and 4,
    # so the second pipe fails. A file then opens only if 3 and 4 were closed.
    source = '''main=():>int64=>{
    let captured=capture("/bin/true" [])
    if captured isnt? SpawnError return 1
    let text=read_text("/etc/passwd")
    return if text is? string 42 else 2
}
'''
    path = tmp_path / 'capture-pipes.udewy'
    path.write_text(codegen(SrcFile(None, source), debug_locations=False))
    assert entry_point(path, [], EntryPointOptions(compile_only=True)) == 0
    limit = lambda: resource.setrlimit(resource.RLIMIT_NOFILE, (5, 5))
    result = subprocess.run([cache_artifact(path).resolve()], preexec_fn=limit, timeout=15, check=False)
    assert result.returncode == 42
