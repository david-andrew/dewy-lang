"""Writable loans reserve once and prove every commit against that reservation."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from tests.python_misc.test_scalar_projection import execute

APPEND = '''append_byte=(@bytes:array<uint8> value:uint8):>void=>{
    $lend(@bytes reserve=1) {
        let address=__load_i64__(bytes)
        __store_u8__(value address+bytes.length)
        bytes.set_length(bytes.length+1)
    }
}
main=():>int64=>{
    let bytes:array<uint8>=[7]
    let old=bytes
    append_byte(@bytes 42)
    if old.length not=?1 or old[0] not=?7 return 1
    return if bytes.length=?2 bytes[1] as int64 else 2
}'''
REPLACE = '''replace_byte=(@bytes:array<uint8>):>void=>{
    if bytes.length=?0 return
    $lend(@bytes) {let address=__load_i64__(bytes) __store_u8__(42 address)}
}
main=():>int64=>{
    let bytes:array<uint8>=[7]
    let old=bytes
    replace_byte(@bytes)
    if old.length not=?1 or old[0] not=?7 return 1
    return if bytes.length=?1 bytes[0] as int64 else 2
}'''
RESERVED = '''fill=(@bytes:array<uint8> count:int64):>void=>{
    if count<?0 or count>?16 return
    $lend(@bytes reserve=count) {
        let address=__load_i64__(bytes)
        let index:int64=0
        loop index<?count {__store_u8__(42 address+bytes.length+index) index+=1}
        bytes.set_length(bytes.length+count)
    }
}
main=():>int64=>{
    let bytes:array<uint8>=[]
    fill(@bytes 3)
    return if bytes.length=?3 bytes[2] as int64 else 1
}'''


@pytest.mark.parametrize('source', [APPEND, REPLACE, RESERVED])
def test_writable_storage_executes(source, tmp_path):
    execute(tmp_path, 'writable-storage', codegen(SrcFile(None, source)))


ERROR_BODIES = [
    'bytes.set_length(0)',
    '$lend(bytes) {bytes.set_length(0)}',
    '$lend(@bytes reserve=1) {bytes.set_length(2)}',
    '$lend(@bytes) {bytes.set_length(-1)}',
    '$lend(@bytes reserve=-1) {}',
    '$lend(@bytes) {__load_i64__(bytes)}',
    '$lend(@bytes) {let address=__load_i64__(bytes) bytes.push(42)}',
    '$lend(@bytes) {let address=__load_i64__(bytes) __syscall3__(0 0 0 1)}',
]


@pytest.mark.parametrize('body', ERROR_BODIES)
def test_writable_storage_rejects_missing_proof(body):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, 'main=():>int64=>{let bytes:array<uint8>=[]\n' + body + '\nreturn 42}'))

KEYWORD = APPEND.replace('bytes.set_length(bytes.length+1)', 'bytes.set_length(count=bytes.length+1)')
PARTIAL = RESERVED.replace('count:int64', 'count:int64 received:int64', 1).replace('if count<?0 or count>?16 return', 'if count<?0 or count>?16 or received<?0 or received>?count return').replace('index<?count', 'index<?received').replace('bytes.length+count)', 'bytes.length+received)').replace('fill(@bytes 3)', 'fill(@bytes 8 3)')


@pytest.mark.parametrize('source', [KEYWORD, PARTIAL])
def test_writable_storage_commit_shapes(source, tmp_path):
    execute(tmp_path, 'writable-commit', codegen(SrcFile(None, source)))


def test_native_writable_storage(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path,
                          cases=[APPEND, REPLACE, RESERVED, KEYWORD, PARTIAL, LIFETIME],
                          errors=[program(body) for body in ERROR_BODIES] + [source for source in REJECTED if "let commit=" not in source])


def program(body):
    return 'main=():>int64=>{let bytes:array<uint8>=[]\n' + body + '\nreturn 42}'

REJECTED = [
    'main=():>int64=>{const bytes:array<uint8>=[]\n$lend(@bytes) {}\nreturn 42}',
    'main=():>int64=>{let bytes:array<uint8<v=>v<?10>>=[]\n$lend(@bytes) {}\nreturn 42}',
    program('$lend(@bytes) {let commit=bytes.set_length}'),
    program('$lend(@bytes reserve=1) {bytes.set_length(1) bytes.set_length(bytes.length+1)}'),
    # A raw write invalidates element evidence that preceded the loan.
    "main=():>int64=>{let bytes:array<uint8>=[7]\nif bytes[0]=?7 {$lend(@bytes) {let address=__load_i64__(bytes) __store_u8__(42 address)}\n$assert bytes[0]=?7}\nreturn 42}",
]

LIFETIME = APPEND[:APPEND.index('main=')] + """
reserve_once=(@calls:int64):>int64<v=>v=?1>=>{calls+=1 return 1}
exercise=():>int64=>{
    let bytes:array<uint8>=[7]
    let before=bytes
    let calls:int64=0
    $lend(@bytes reserve=reserve_once(@calls)) {
        let address=__load_i64__(bytes)
        __store_u8__(41 address+bytes.length)
        bytes.set_length(bytes.length+1)
    }
    if calls not=?1 return 1
    append_byte(@bytes 42)
    if before.length not=?1 or before[0] not=?7 return 2
    return if bytes.length=?3 bytes[2] as int64 else 3
}
main=():>int64=>{
    if exercise() not=?42 return 4
    let before:int64=_arena_live_bytes
    loop i in [0..100) {if exercise() not=?42 return 5}
    return if _arena_live_bytes=?before 42 else 6
}
"""


@pytest.mark.parametrize('source', REJECTED)
def test_writable_storage_rejects_aliases_and_stale_facts(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))


def test_writable_storage_reclaims_storage_and_evaluates_reserve_once(tmp_path):
    execute(tmp_path, 'writable-lifetime', codegen(SrcFile(None, LIFETIME)))
