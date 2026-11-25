"""Record a compiler invocation's status, diagnostics and program behavior.

Record text outputs directly and run host executables. Store the format of
cross-target images, whose execution is covered by the host matrix.
"""
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

from tests import leaf_oracle

RUN_SECONDS = 2
LADDER_RUNTIME_ONLY = {'95_kv_store', '96_ct_crypto'}
# ELF e_machine of native Linux executables.
HOST_MACHINE = ({'x86_64': 62, 'amd64': 62, 'aarch64': 183, 'arm64': 183}.get(platform.machine().lower())
                if sys.platform.startswith('linux') else None)
CONCURRENCY = re.compile(
    rb'\b(?:parallel(?:_map|_range|_update)?|concurrent|tasks?|spawn(?:_detached)?|channels?|threads?|mpmc|spsc)\b',
    re.I,
)
SOURCE_IMPORT = re.compile(rb'''(?:\bfrom\s+p|\bimport\s+p|^\s*use\s+)["']([^"'\n]+\.(?:dewy|jo))["']''', re.M)
PLAIN_TEXT = re.compile(rb'''"(?:[^"\\{\r\n]|\\.)*"|'(?:[^'\\{\r\n]|\\.)*'|#(?!\{)[^\r\n]*''')
SELF_WARNING = re.compile(rb'^<(?:root|tmp)>(?:/[^:\n]*)?/(?:compiler|lib)/[^:\n]+:\d+:\d+: warning:')
FUSED_TRACE = re.compile(rb'^\s*fused worker(?: |:)')


def _text(tmp, data):
    return leaf_oracle.without(tmp, data).decode(errors='surrogateescape')


def _source(arguments):
    for argument in arguments:
        source = Path(os.fsdecode(argument))
        if source.suffix in ('.dewy', '.jo') and source.is_file():
            return source
    return None


def _native(source):
    """Web-only cases and ladder stress workloads run in their own suites."""
    if source is not None:
        if source.parent.name in LADDER_RUNTIME_ONLY:
            return False
        with source.open('rb') as stream:
            for line in stream:
                if not line.startswith(b'#'):
                    break
                if line.startswith(b'# modes:'):
                    return any(mode.startswith(b'native') for mode in line.split()[2:])
    return True


def _concurrent(source):
    """Include explicit local imports, which may start workers on the entry file's behalf."""
    seen = set()
    pending = [] if source is None else [source.resolve()]
    while pending:
        path = pending.pop()
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        code = re.sub(rb'(?m)^\s*#(?!\{).*$', b'', path.read_bytes())
        if CONCURRENCY.search(PLAIN_TEXT.sub(b' ', code)):
            return True
        for name in SOURCE_IMPORT.findall(code):
            if name.startswith(b'@lib/'):
                library = Path(os.environ.get('DEWY_CORE_LIB', leaf_oracle.ROOT / 'lib'))
                pending.append((library / os.fsdecode(name[5:])).resolve())
            elif not name.startswith(b'@'):
                pending.append((path.parent / os.fsdecode(name)).resolve())
    return False


def _one_cpu():
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})


def _run(path, tmp, setup=None):
    try:
        ran = subprocess.run([path], cwd=tmp, stdin=subprocess.DEVNULL, capture_output=True,
                             timeout=RUN_SECONDS, check=False, preexec_fn=setup)
    except subprocess.TimeoutExpired:
        return 'timeout'
    return {'status': ran.returncode, 'stdout': _text(tmp, ran.stdout), 'stderr': _text(tmp, ran.stderr)}


def made(path, tmp, runs=True, concurrent=False):
    """The record of one file a build made."""
    with path.open('rb') as stream:
        header = stream.read(20)
    if header.startswith(b'\x7fELF'):
        if not runs or int.from_bytes(header[18:20], 'little') != HOST_MACHINE or not os.access(path, os.X_OK):
            return {'binary': 'elf'}
        first = _run(path, tmp)
        if concurrent and first != 'timeout' and hasattr(os, 'sched_setaffinity'):
            second = _run(path, tmp, _one_cpu)
            if second == 'timeout':
                first['one_cpu_status'] = 'timeout'
            elif first != second:
                first['one_cpu_status'] = second['status']
                for stream in ('stdout', 'stderr'):
                    if first[stream] != second[stream]:
                        first[stream] = {'varies': True}
        return {'run': first}
    for magic, kind in ((b'MZ', 'pe'), (b'\0asm', 'wasm'), (b'\xcf\xfa\xed\xfe', 'macho')):
        if header.startswith(magic):
            return {'binary': kind}
    if path.suffix == '.html':
        return {'format': 'html'}
    data = path.read_bytes()
    if b'\0' in data:
        return {'binary': 'data'}
    return {'text': _text(tmp, data)}


def build(arguments, status, stdout, stderr, files, tmp, *, run_outputs=True):
    """The record of one build: arguments, status, output, diagnostics and the files it made."""
    names = [os.fsdecode(a) for a in arguments]
    source = _source(names) if status == 0 and (files or b'warning:' in stderr) else None
    stderr = leaf_oracle.without(tmp, stderr)
    if source is not None and source.name == 'main.jo' and source.parent.name == 'compiler':
        stderr = b''.join(line for line in stderr.splitlines(keepends=True) if not SELF_WARNING.match(line))
    if os.environ.get('DEWY_FUSED_TRACE'):
        stderr = b''.join(line for line in stderr.splitlines(keepends=True) if not FUSED_TRACE.match(line))
    # A rejected build can leave an earlier program in place.
    outputs = {}
    if status == 0 and files:
        runs = run_outputs and _native(source)
        concurrent = runs and _concurrent(source)
        outputs = {path.name: made(path, tmp, runs, concurrent) for path in files}
    return {'args': [_text(tmp, os.fsencode(a)) for a in names], 'status': status,
            'stdout': '' if '--ir' in names or '--host-ir' in names else _text(tmp, stdout),
            'stderr': stderr.decode(errors='surrogateescape'), 'files': outputs}


def outputs(target):
    """The files a build to `target` made (a Windows build adds .exe and .pdb)."""
    target = Path(target)
    return sorted(p for p in target.parent.glob(target.name + '*')
                  if p.is_file() and p.suffix not in ('.dewy', '.jo'))
