"""Scoped raw reads retain an owner without permanently pinning its storage."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from tests.python_misc.test_scalar_projection import execute

FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures'
READ = (FIXTURES / 'scoped_storage_read.dewy').read_text()
WRITE = (FIXTURES / 'scoped_storage_write.dewy').read_text()
KERNEL = (FIXTURES / 'scoped_storage_kernel.dewy').read_text()


def program(body, prefix=''):
    return prefix + 'main=():>int64=>{let bytes:array<uint8>=[42]\n' + body + '\nreturn 42}'


ERRORS = [
    program('$lend(bytes) {__load_i64__(bytes)}'),
    program('$lend(bytes) {let address=__load_i64__(bytes) return address}'),
    program('let saved:int64=0\n$lend(bytes) {saved=__load_i64__(bytes)}'),
    program('$lend(bytes) {let address=__load_i64__(bytes) sink(address)}', 'sink=(word:int64):>void=>{}\n'),
    program('$lend(bytes) {bytes.push(1)}'),
    program('$lend(bytes) {let address=__load_i64__(bytes) __store_u8__(0 address)}'),
    program('$lend(bytes) {let address=__load_i64__(bytes) __syscall3__(0 0 address 1)}'),
    program('$lend(bytes) {let first=__load_i64__(bytes) let next=first+1 next}'),
    program('$lend(bytes) {let first=__load_i64__(bytes) let next=first transmute uint64 next}'),
    program('$lend(bytes) {let first=__load_i64__(bytes) let callback=()=>first}'),
    program('$lend(bytes) {let first=__load_i64__(bytes) let stored=[first]}'),
    program('$lend(bytes) {let first:int64=0 let second:int64=0\nloop true {first=second second=__load_i64__(bytes) break}\nfirst}'),
]


@pytest.mark.parametrize('source', [READ, WRITE, KERNEL])
def test_scoped_read_executes_without_retaining_storage(tmp_path, source):
    results = execute(tmp_path, 'scoped-storage', codegen(SrcFile(None, source)))
    if source == WRITE:
        assert all(result.stdout == 'abc' for result in results)


@pytest.mark.parametrize('source', ERRORS)
def test_scoped_read_requires_complete_lifetime_evidence(source):
    with pytest.raises(ReportException, match='cannot prove scoped storage access'):
        codegen(SrcFile(None, source))


def test_native_scoped_reads(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path,
                          cases=[READ, WRITE, KERNEL], errors=ERRORS, outputs=['', 'abc', ''])
