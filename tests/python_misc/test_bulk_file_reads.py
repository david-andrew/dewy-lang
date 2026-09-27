"""Bulk reads preserve bytes, short final chunks, errors and buffer lifetimes."""
import json
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from tests.python_misc.test_scalar_projection import execute


def source_for(tmp_path):
    path = tmp_path / 'bulk-input.bin'
    path.write_bytes(bytes(range(256)) * 36 + b'*')
    empty = tmp_path / 'empty-input.bin'
    empty.write_bytes(b'')
    return f'''
exercise=():>int64=>{{
    let bytes=read_bytes({json.dumps(str(path))})
    if bytes isnt? array<uint8> return 1
    if bytes.length not=?9217 return 2
    loop i in [0..9216) {{if bytes[i] not=? ((i % 256) as uint8) return 3}}
    if bytes[9216] not=?42 return 4
    let old=bytes
    bytes[0]=42
    if old[0] not=?0 return 5
    let empty=read_bytes({json.dumps(str(empty))})
    if empty isnt? array<uint8> or empty.length not=?0 return 6
    let missing=read_bytes({json.dumps(str(tmp_path / 'absent.bin'))})
    if missing isnt? FileNotFound return 7
    let directory=read_bytes({json.dumps(str(tmp_path))})
    if directory isnt? IsDirectory return 8
    return 42
}}
main=():>int64=>{{
    if exercise() not=?42 return 9
    let before:int64=_arena_live_bytes
    loop i in [0..10) {{if exercise() not=?42 return 10}}
    return if _arena_live_bytes=?before 42 else 11
}}
'''


def test_bulk_reads_release_storage(tmp_path):
    execute(tmp_path, 'bulk-reads', codegen(SrcFile(None, source_for(tmp_path))))


def test_native_bulk_reads(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[source_for(tmp_path)], errors=[])
