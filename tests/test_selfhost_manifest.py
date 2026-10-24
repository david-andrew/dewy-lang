"""compiler/manifest.dewy, a program's packages as text (the build block's specs, dewy.lock's
pins, a URL's directory and default name): it ships, and its frozen implementation-language
twin compiler/manifest.jo gives the same answers. The oracle is the rules below, on bytes:
a build block starts at a line `build:` and runs while its lines are indented (blank and
comment lines are skipped); a spec line is `name = package("src")` or
`name = package("src", "ref")`, the first spec of a name wins; trimming drops spaces, tabs
and line breaks; a commit is 40 lowercase hexadecimal digits."""
import random
import re
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/selfhost'
SPACE = b' \t\n\r'
HEADER = (b"# the commits of the packages in this program's build block (dewy-core build writes this: keep it\n"
          b"# with the program; delete a line to take the newest commit again)\n")


def block_at(src):
    if src.startswith(b'build:'):
        return 0
    k = src.find(b'\nbuild:')
    return k + 1 if k >= 0 else -1


def strings(s):
    out = []
    i = 0
    while i < len(s) and s[i:i + 1] != b')':
        if s[i:i + 1] == b'"':
            e = s.find(b'"', i + 1)
            if e < 0:
                break
            out.append(s[i + 1:e])
            i = e
        i += 1
    return out


def scan(specs, path, src, at):
    if at < 0:
        return
    s = max(path.rfind(b'/'), path.rfind(b'\\'))
    d = path[:s] if s >= 0 else b'.'
    lines = src[at:].split(b'\n')[1:]
    for line in lines:
        t = line.strip(SPACE)
        if not t or t.startswith(b'#'):
            continue
        if line[:1] not in (b' ', b'\t'):
            break
        name, eq, val = t.partition(b'=')
        val = val.strip(SPACE)
        if not eq or not val.startswith(b'package('):
            continue
        args = strings(val[8:])
        if not args:
            continue
        spec = (name.strip(SPACE), args[0], args[1] if len(args) > 1 else b'', d)
        if all(q[0] != spec[0] for q in specs):
            specs.append(spec)


def is_git(src):
    return b'://' in src or any(src.startswith(p) for p in (b'git@', b'github.com/', b'gitlab.com/', b'codeberg.org/'))


def url(src):
    return src if b'://' in src or src.startswith(b'git@') else b'https://' + src


def is_commit(ref):
    return re.fullmatch(rb'[0-9a-f]{40}', ref) is not None


def dir_name(u):
    k = u.find(b'://')
    if k >= 0:
        u = u[k + 3:]
    return bytes(c if chr(c).isascii() and (chr(c).isalnum() or c in b'_.-') or c >= 0x80 else ord('_') for c in u)


def default_name(src):
    n = src.rstrip(b'/')
    n = n[max(n.rfind(b'/'), n.rfind(b':')) + 1:]
    if n.endswith(b'.git'):
        n = n[:-4]
    if n.startswith(b'dewy-'):
        n = n[5:]
    return n.replace(b'-', b'_')


def remote_lines(out):
    for line in out.split(b'\n'):
        sha, tab, rest = line.partition(b'\t')
        if tab and is_commit(sha):
            yield sha, rest.strip(SPACE)


def remote_names(out, want):
    names = []
    for _, ref in remote_lines(out):
        name = ref[:-3] if ref.endswith(b'^{}') else ref
        if name in (want, b'refs/' + want, b'refs/tags/' + want, b'refs/heads/' + want) and name not in names:
            names.append(name)
    return names


def remote_commit(out, want):
    names = remote_names(out, want)
    if len(names) != 1:
        return b''
    lines = list(remote_lines(out))
    peeled = [sha for sha, ref in lines if ref == names[0] + b'^{}']
    return (peeled or [sha for sha, ref in lines if ref == names[0]])[0]


def lock_key(name, u, ref):
    return b'%s %s %s' % (name, u, ref)


def lock_read(text):
    locked = {}
    for line in text.split(b'\n'):
        parts = line.strip(SPACE).split(b' ')
        if len(parts) == 4 and not parts[0].startswith(b'#') and is_commit(parts[3]):
            locked[lock_key(parts[0], parts[1], b'' if parts[2] == b'-' else parts[2])] = parts[3]
    return locked


def insert(text, name, src):
    nl = b'\r\n' if b'\r\n' in text else b'\n'
    line = b'    %s = package("%s")%s' % (name, src, nl)
    at = block_at(text)
    if at < 0:
        return b'build:' + nl + line + nl + text
    e = text.find(b'\n', at)
    if e < 0:
        return text + nl + line
    return text[:e + 1] + line + text[e + 1:]


def b(x):
    return b'true' if x else b'false'


def expected(texts):
    out = []
    every = []
    for t in texts:
        at = block_at(t)
        specs = []
        scan(specs, b'pkgs/a\\b/main.jo', t, at)
        had = len(every)
        scan(every, t, t, at)
        out.append(b'<%d %d' % (at, len(every) - had))
        out += [b'  spec ' + b'|'.join(s) for s in specs]
        out += [b'  all ' + b'|'.join(s) for s in every]
        out.append(b'  strings ' + b'|'.join(strings(t)))
        out.append(b'  git %s %s %s %s %s %s %s' % (
            b(is_git(t)), url(t), b(t.startswith(b'-') or b' ' in t), b(t.startswith(b'-') or b' ' in t),
            b(is_commit(t)), dir_name(t), default_name(t)))
        if is_commit(t):
            out.append(b'  commit %s /cache/%s@%s' % (t[:12], dir_name(b'https://h/x'), t[:12]))
        out.append(b'  remote %s %s %s' % (remote_commit(t, b'v1.2'), remote_commit(t, b'HEAD'), b'|'.join(remote_names(t, b'v1.2'))))
        locked = lock_read(t)
        out.append(b'  locked %d' % len(locked))
        for line in t.split(b'\n'):
            parts = line.strip(SPACE).split(b' ')
            if len(parts) == 4:
                ref = b'' if parts[2] == b'-' else parts[2]
                key = lock_key(parts[0], parts[1], ref)
                out.append(b'  lock %s %s %s %s %s' % (key, locked.get(key, b'none'), parts[0], parts[1],
                                                         b'%s %s' % (ref or b'-', parts[3])))
        out.append(HEADER + b'\n'.join(sorted(t.split(b'\n'))) + b'\n')
        out.append(b'  declares %s %s' % (b(b'\n    physics = package(' in t or b'\n\tphysics = package(' in t),
                                          b(b'\n    x = package(' in t or b'\n\tx = package(' in t)))
        out.append(insert(t, b'physics', b'https://github.com/ann/dewy-physics'))
        out.append(b'>')
    return b'\n'.join(out) + b'\n'


NAMES = ['physics', 'tween', 'shared', 'x', 'é', 'a_b', 'dewy-net', '', 'two words', 'p#q']
SOURCES = ['https://github.com/ann/dewy-physics', 'github.com/bob/tween', 'gitlab.com/c/d.git', 'codeberg.org/e/f/',
           'git@github.com:g/dewy-h-i.git', '../shared', '/abs/dir', 'C:/win/dir', 'dir\\sub', '-upload', 'a b',
           'ssh://host:22/x', 'https://ünï.code/日本/dewy-語.git', 'file:///tmp/x', '', 'https://h/x?y=1&z#w']
REFS = ['', 'v1.2', 'main', '-x', 'a b', '0123456789abcdef0123456789abcdef01234567',
        '0123456789ABCDEF0123456789abcdef01234567', 'refs/tags/v1^{}']
COMMITS = ['0123456789abcdef0123456789abcdef01234567', '0123456789abcdef0123456789abcdef01234567', 'fedcba9876543210fedcba9876543210fedcba98',
           '0123456789abcdef', 'zz', '0123456789abcdef0123456789abcdef0123456g', 'é' * 40]


def spec_line(rng):
    indent = rng.choice(['    ', '\t', '  ', ' \t', '', '        '])
    name = rng.choice(NAMES)
    eq = rng.choice([' = ', '=', ' =', '= ', ' : ', ' == '])
    args = [f'"{rng.choice(SOURCES)}"'] + [f'"{rng.choice(REFS)}"' for _ in range(rng.choice([0, 0, 1, 1, 2]))]
    sep = rng.choice([', ', ',', ' ', ''])
    call = rng.choice(['package(', 'package (', 'packages(', 'pkg(', 'package('])
    close = rng.choice([')', ')', '', ') # pinned', ')"x"'])
    if rng.random() < 0.1:
        args[0] = args[0][:-1]
    return indent + name + eq + call + sep.join(args) + close


def manifest(rng):
    lines = []
    for _ in range(rng.randrange(0, 4)):
        lines.append(rng.choice(['x = 1', 'main = ():', '# build:', '    print(1)', 'use "a.jo"', '']))
    lines.append(rng.choice(['build:', 'build:', 'build: # packages', 'xbuild:', ' build:', 'build']))
    for _ in range(rng.randrange(0, 7)):
        r = rng.random()
        if r < 0.65:
            lines.append(spec_line(rng))
        elif r < 0.75:
            lines.append(rng.choice(['    # a comment', '', '   ', '\t# tab']))
        elif r < 0.85:
            lines.append(rng.choice(['    target = "x86_64-linux"', '    mode = "release"', '    name = "game"']))
        else:
            lines.append(rng.choice(['main = ():', 'x = package("https://top/level")', 'build:']))
    nl = rng.choice(['\n', '\n', '\r\n'])
    return nl.join(lines) + rng.choice(['', nl])


def lock(rng):
    lines = []
    for _ in range(rng.randrange(0, 6)):
        r = rng.random()
        if r < 0.7:
            parts = [rng.choice(NAMES) or 'n', rng.choice(SOURCES) or 'u', rng.choice(REFS) or '-', rng.choice(COMMITS)]
            if rng.random() < 0.1:
                parts = parts[:rng.randrange(1, 4)] + (['extra'] if rng.random() < 0.5 else [])
            lines.append(rng.choice(['', ' ', '\t']) + ' '.join(parts) + rng.choice(['', ' ', '\r']))
        else:
            lines.append(rng.choice(['# the commits', '', '#x y z w']))
    return '\n'.join(lines) + rng.choice(['', '\n'])


def remote(rng):
    lines = []
    for _ in range(rng.randrange(0, 5)):
        sha = rng.choice(COMMITS)
        ref = rng.choice(['HEAD', 'refs/heads/main', 'refs/tags/v1.2', 'refs/tags/v1.2^{}', 'refs/tags/x^{} ',
                         'refs/heads/v1.2', 'refs/heads/a/v1.2', 'v1.2', 'refs/v1.2', 'refs/tags/v1.2 '])
        lines.append(sha + rng.choice(['\t', '\t', ' ', '\t\t']) + ref)
    return '\n'.join(lines)


FIXED = [
    'build:\n    physics = package("https://github.com/ann/dewy-physics")\n',
    'x = 1\nbuild:\n    a = package("../a")\n    b = package("git@h:b.git", "v2")\n    a = package("../other")\nmain = ():\n'
    '    c = package("not/in/block")\n',
    'build:', 'build:\n', '\nbuild:\n\tt = package("https://t")', 'no block here', '', ' ', 'build:\r\n    w = package("https://w")\r\n',
    '0123456789abcdef0123456789abcdef01234567\tHEAD\n0123456789abcdef0123456789abcdef01234568\trefs/tags/v1^{}',
    '0123456789abcdef0123456789abcdef01234567\trefs/heads/a/v1.2\nfedcba9876543210fedcba9876543210fedcba98\trefs/tags/v1.2\n'
    '0123456789abcdef0123456789abcdef01234568\trefs/tags/v1.2^{}',
    '0123456789abcdef0123456789abcdef01234567\trefs/heads/v1.2\nfedcba9876543210fedcba9876543210fedcba98\trefs/tags/v1.2',
    '0123456789abcdef0123456789abcdef01234567', 'https://github.com/ann/dewy-physics.git///', 'dewy-', '/', ':', '.git',
    'p https://p - 0123456789abcdef0123456789abcdef01234567\nq https://q v1 fedcba9876543210fedcba9876543210fedcba98',
    'p https://p v1 zzzz\nq https://q - 0123456789ABCDEF0123456789abcdef01234567\nr https://r v2 fedcba9876543210fedcba9876543210fedcba98',
    'build:\n    é = package("https://ü/ñ", "β")\n    "q" = package("\\"")\n    e = package()\n    f = package(")")\n',
    '-', '--upload-pack=x', 'a b', 'git@x', 'https://a b',
]


MALFORMED = [b'build:\n    a = package("\x80/sh", "\xbf")\n\x80x = package("y")\n',
             b'build:\n    \xbfz = \x80package("x")\n    w =\xbf package("y")\n    v = package(\xbf"q")\n',
             b'https://\x80\xff/a b', b'git@h:\xbf', b'dewy-\xc3/', b'\xc3', b'build:\n\xc3\xa9 = package("x")\n',
             b'0123456789abcdef0123456789abcdef01234567\t\x80^{}', b'p https://\xff - 0123456789abcdef0123456789abcdef01234567']


def texts():
    rng = random.Random(20261024)
    out = list(FIXED)
    for _ in range(200):
        out.append(rng.choice([manifest, manifest, manifest, lock, remote])(rng))
    alphabet = 'build:\n \t"()=#-/\\:@.^{}xé\r0af'
    for _ in range(80):
        out.append(''.join(rng.choice(alphabet) for _ in range(rng.randrange(0, 40))))
    out = [t.encode() for t in out]
    # (malformed UTF-8 passes through, as the compiler's sources may hold it)
    out += MALFORMED
    for t in out[len(FIXED):len(FIXED) + 60]:
        t = bytearray(t)
        for _ in range(rng.randrange(1, 4)):
            t.insert(rng.randrange(0, len(t) + 1), rng.randrange(0x80, 0x100))
        out.append(bytes(t))
    return out


def build(compiler, source, binary, release):
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    return binary


def run(binary, words):
    ran = subprocess.run([binary, *words], capture_output=True, timeout=60)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    return ran.stdout


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_manifest_matches_jo(compiler, tmp_path, release):
    words = texts()
    dewy = build(compiler, FIXTURES / 'manifest_dewy.dewy', tmp_path / 'manifest-dewy', release)
    jo = build(compiler, FIXTURES / 'manifest_jo.jo', tmp_path / 'manifest-jo', release)
    got = run(dewy, words)
    assert got == run(jo, words)
    assert got == expected(words)


@pytest.mark.core_quick
def test_selfhost_manifest_ships_dewy(compiler):
    binary = compiler.read_bytes()
    assert b'/compiler/manifest.dewy\0' in binary
    assert b'/compiler/manifest.jo\0' not in binary
