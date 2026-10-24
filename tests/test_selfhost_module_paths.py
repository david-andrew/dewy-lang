"""compiler/module_paths.dewy (paths as the compiler keeps them, a module's identity, the file an
import names and the files a named import may be, the language server's file URIs, the run
cache's name hash): it ships, and its frozen implementation-language twin
compiler/module_paths.jo gives the same answers. One Sloppy driver runs over either module, so
paths can be any bytes; the oracle is the rules below, on bytes."""
import random
import subprocess
import urllib.parse
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / 'tests/fixtures/selfhost/module_paths_jo.jo'
FILES = ', '.join(f'`{n}`' for n in ['read_file', 'list_dir', 'walk_dir', 'glob', 'make_dirs', 'rename_file',
                                       'join_path'])
WHEN = '`time()`, `unix_time()`, `now()` (a Date) and `sleep(s)` are there without an import'
MATH = '`random()`, `random_int(lo, hi)`, `sqrt`, `floor`, `PI` are there without an import'
HINTS = {
    're': 'regular expressions are there without an import, `regex(r"\\d+")`',
    'sys': '`args()` is the command line, `exit(code)` ends the program',
    'json': '`parse_json(s)` and `to_json(x)` are there without an import',
    **{m: f'files are there without an import: {FILES}' for m in ['os', 'shutil', 'pathlib', 'glob']},
    'time': WHEN, 'datetime': WHEN, 'random': MATH, 'math': MATH,
    'csv': '`csv_rows(text)` is there without an import',
    'collections': 'maps start missing keys at zero (`counts[w] += 1`); `sorted_by`, `unique`, `group_by`',
    'subprocess': '`run_program("ls", ["-l"])` (its exit code and output)',
    'argparse': 'a struct of the options (`verbose = false`, `out = "a.txt"`, `files: str[]`), then '
                '`opts = parse_args[Options]("what it does")`',
    'hashlib': '`sha256(text_or_bytes)` is there without an import (as hex digits)',
}


def is_abs(p):
    return p.startswith(b'/') or p[1:3] == b':/'


def strip_ext(p):
    dot = p.rfind(b'.')
    return p if dot <= p.rfind(b'/') + 1 else p[:dot]


def windows(p):
    q = p.replace(b'\\', b'/')
    return q[:1].lower() + q[1:] if q[1:2] == b':' and q[:1].isupper() else q


def normal(p):
    # (nothing for norm to do, as the compiler checks before it: not empty, no trailing slash,
    # not starting with a dot, and no empty, . or .. part after the first)
    if not p or p.endswith(b'/') or p.startswith(b'.'):
        return False
    return all(part not in (b'', b'.', b'..') for part in p.split(b'/')[1:])


def norm(p):
    if normal(p):
        return p
    parts = []
    for part in p.split(b'/'):
        if part in (b'', b'.'):
            continue
        if part == b'..':
            parts = parts[:-1]
            continue
        parts.append(part)
    out = b'/'.join(parts)
    if p.startswith(b'//') and not p.startswith(b'///'):
        return b'//' + out
    return b'/' + out if p.startswith(b'/') else out


def hexval(c):
    try:
        return int(bytes([c]), 16)
    except ValueError:
        return 0


def uri_path(u):
    s = u
    if s.startswith(b'file://'):
        s = s[7:]
        if s and not s.startswith(b'/'):
            s = b'//' + s
    out = bytearray()
    i = 0
    while i < len(s):
        if s[i] == ord('%') and i + 2 < len(s):
            out.append(hexval(s[i + 1]) * 16 + hexval(s[i + 2]))
            i += 3
        else:
            out.append(s[i])
            i += 1
    return bytes(out[1:]) if out[:1] == b'/' and out[2:3] == b':' else bytes(out)


def to_uri(p):
    head = b'file:' if p.startswith(b'//') else b'file://' if p.startswith(b'/') else b'file:///'
    return head + urllib.parse.quote_from_bytes(p, safe='/').encode()


def fnv(p):
    h = 2166136261
    for c in p:
        h = ((h ^ c) * 16777619) % 2 ** 32
    return ''.join('0123456789abcdef'[(h >> (4 * k)) & 15] for k in range(8)).encode()


def expected(p):
    s = p.find(b'/')
    package = p[:s] if s > 0 else b''
    if p.startswith(b'@lib/'):
        use, bare = b'L/' + p[5:], b'L/' + p[5:]
    else:
        use, bare = (p if is_abs(p) else b'D/' + p), p
    rows = [b'=== ' + p, b'1' if is_abs(p) else b'0', strip_ext(p), p, windows(p), b'1' if normal(p) else b'0', norm(p),
            p[:p.rfind(b'/')] if b'/' in p else b'.', strip_ext(p[p.rfind(b'/') + 1:]),
            norm(p if is_abs(p) else b'/cwd/' + p), norm(p if is_abs(p) else b'cwd/./x/../' + p), use, bare, package]
    if package:
        rows.append(b'P/' + p[s + 1:])
    rows += [p + b'.dewy|' + p + b'.jo', p + b'.jo|' + p + b'.dewy',
             b'|'.join(d + b'/' + p for d in [b'D', b'L', b'L/std', b'L/game', b'L/core']),
             (': ' + HINTS[p.decode()]).encode() if p.decode('latin-1') in HINTS else b'',
             uri_path(p), to_uri(p), fnv(p)]
    return b''.join(r + b'\n' for r in rows)


def paths():
    out = [b'', b'.', b'..', b'/', b'//', b'///', b'x', b'.x', b'a/.x', b'a/..x', b'a/...', b'x.tar.gz', b'.bashrc',
           b'dir.d/name', b'/a/b/../c.jo', b'a/./b//c/', b'../../up', b'a/b/../../..', b'//server/share/x',
           b'///x/./y', b'@lib/std/json.jo', b'@lib/', b'c:/x/y.dewy', b'c:', b'c:x', b'C:/X', b'/c:/x',
           b'file:///c%3A/x%20y', b'file://server/share', b'file:///a/%C3%A9.jo', b'file://', b'file:',
           b'file:/x', b'%41%zz%', b'%4', b'%e9x', b'pkg/file.jo', b'/pkg/file.jo', b'pkg/', b'\xc3\xa9/\xc3\xbc.jo',
           b'a/\x80b/\xffc.jo', b'\x80.\xff', b'a b~c-d_e', b'back\\slash.jo', b'C:\\x\\y.jo', b'Z:', b'a:\\', b'\\\\unc\\share', *[k.encode() for k in HINTS],
           b'Re', b'os.path']
    out += [str(p.relative_to(ROOT)).encode() for p in sorted((ROOT / 'compiler').glob('*'))[:40]]
    rng = random.Random(12)
    pieces = [b'a', b'bc', b'.', b'..', b'/', b'//', b'@lib/', b'c:', b'C:', b'%41', b'%2F', b'%3a', b'%zz', b'%',
              b'file://', b'\xc3\xa9', b'\x80', b'\xff', b'-', b'~', b' ', b'\\', b'.jo', b'.dewy', b'x_y', b'_']
    for _ in range(400):
        out.append(b''.join(rng.choice(pieces) for _ in range(rng.randrange(1, 9))))
    return out


def build(compiler, source, binary, release):
    built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    return binary


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_module_paths_match_jo(compiler, tmp_path, release):
    driver = DRIVER.read_text()
    twin = "use '../../../compiler/module_paths.jo'"
    assert twin in driver
    outputs = []
    for module in ('module_paths.dewy', 'module_paths.jo'):
        source = tmp_path / f'driver-{module.replace(".", "-")}.jo'
        source.write_text(driver.replace(twin, f"use '{ROOT / 'compiler' / module}'"))
        binary = build(compiler, source, tmp_path / source.stem, release)
        corpus = tmp_path / 'paths'
        corpus.write_bytes(b'\n'.join(paths()))
        ran = subprocess.run([binary, corpus], capture_output=True, timeout=60)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    want = b''.join(expected(p) for p in paths())
    got = outputs[0].split(b'\n=== ')
    for g, w in zip(got, want.split(b'\n=== ')):
        assert g == w
    assert outputs[0] == want


@pytest.mark.core_quick
def test_selfhost_module_paths_ship_dewy(compiler, tmp_path):
    binary = compiler.read_bytes()
    assert b'/compiler/module_paths.dewy\0' in binary
    assert b'/compiler/module_paths.jo\0' not in binary
    (tmp_path / 'sub').mkdir()
    (tmp_path / 'x').mkdir()
    (tmp_path / 'sub/helper.dewy').write_text('f=():>int64=>42\n')
    main = tmp_path / 'main.dewy'
    main.write_text('from p"./x/../sub/helper.dewy" import f\nmain=():>void=>printl(f())\n')
    ran = subprocess.run([compiler, 'run', main], capture_output=True, text=True, timeout=60)
    assert ran.returncode == 0 and ran.stdout == '42\n', ran.stdout + ran.stderr
    main.write_text('import argparse\nmain=():>void=>printl(1)\n')
    checked = subprocess.run([compiler, 'check', main], capture_output=True, text=True, timeout=60)
    assert checked.returncode != 0
    assert "cannot find module 'argparse': a struct of the options" in checked.stdout + checked.stderr
