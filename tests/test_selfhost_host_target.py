"""The host's target name and executable headers match frozen Jo."""
import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401

DRIVER = r'''
main = ():
    loop path in ["elf_x64", "elf_arm64", "macho", "macho_x64", "short", "missing", "empty"]: print(elf_machine_of(path))
    print(host_target_name())
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_host_target_twins(compiler, tmp_path, release):  # noqa: F811
    run = tmp_path / 'run'
    run.mkdir()
    header = bytes(18)
    (run / 'elf_x64').write_bytes(header + b'\x3e\x00' + bytes(4))
    (run / 'elf_arm64').write_bytes(header + b'\xb7\x00')
    (run / 'macho').write_bytes(b'\xcf\xfa\xed\xfe\x0c\x00\x00\x01' + bytes(12))
    (run / 'macho_x64').write_bytes(b'\xcf\xfa\xed\xfe\x07\x00\x00\x01' + bytes(32))
    (run / 'short').write_bytes(bytes(19))
    (run / 'empty').write_bytes(b'')
    output = compare_narrow(compiler, tmp_path, release, ('host_target',), DRIVER, run_in=lambda: run)
    assert output.split() == [b'62', b'183', b'16777228', b'16777223', b'0', b'0', b'0', b'x86_64-linux']
