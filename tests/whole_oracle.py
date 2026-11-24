"""Record a compiler invocation's status, diagnostics and program behavior.

Record text outputs directly and run host executables. Store the format of
cross-target images, whose execution is covered by the host matrix.
"""
import os
import platform
import subprocess
from pathlib import Path

from tests import leaf_oracle

RUN_SECONDS = 30
# (ELF e_machine of the executables this host runs)
HOST_MACHINE = {'x86_64': 62, 'amd64': 62, 'aarch64': 183, 'arm64': 183}.get(platform.machine().lower())


def _text(tmp, data):
    return leaf_oracle.text_or_digest(leaf_oracle.without(tmp, data))


def native(arguments):
    """Whether the program runs natively: a golden case may be meant for the web modes alone."""
    for argument in arguments:
        source = Path(os.fsdecode(argument))
        if source.suffix in ('.dewy', '.jo') and source.is_file():
            # (95_kv_store fsyncs 3000 transactions ~22s/run; the ladder suite runs it)
            if source.parent.name == '95_kv_store':
                return False
            for line in source.read_text(errors='replace').splitlines():
                if not line.startswith('#'):
                    break
                if line.startswith('# modes:'):
                    return any(mode.startswith('native') for mode in line.split()[2:])
    return True


def _one_cpu():
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})


def _run(path, tmp, setup=None):
    try:
        ran = subprocess.run([path], cwd=tmp, stdin=subprocess.DEVNULL, capture_output=True,
                             timeout=RUN_SECONDS, check=False, preexec_fn=setup)
    except subprocess.TimeoutExpired:
        return 'timeout'
    return {'status': ran.returncode, 'stdout': _text(tmp, ran.stdout), 'stderr': _text(tmp, ran.stderr)}


def made(path, tmp, runs=True):
    """The record of one file a build made."""
    data = path.read_bytes()
    if data.startswith(b'\x7fELF'):
        if not runs or int.from_bytes(data[18:20], 'little') != HOST_MACHINE or not os.access(path, os.X_OK):
            return {'binary': 'elf'}
        # (run twice, the second time on one CPU: output that depends on the time, the machine or its
        # CPU count is recorded only as varying)
        first, second = _run(path, tmp), _run(path, tmp, _one_cpu)
        return {'run': first if first == second else 'varies'}
    for magic, kind in ((b'MZ', 'pe'), (b'\0asm', 'wasm'), (b'\xcf\xfa\xed\xfe', 'macho')):
        if data.startswith(magic):
            return {'binary': kind}
    if b'\0' in data:
        return {'binary': 'data'}
    return {'text': _text(tmp, data)}


def build(arguments, status, stdout, stderr, files, tmp):
    """The record of one build: arguments, status, output, diagnostics and the files it made."""
    names = (os.fsdecode(a) for a in arguments)
    return {'args': [leaf_oracle.without(tmp, os.fsencode(a)).decode(errors='surrogateescape') for a in names],
            'status': status, 'stdout': _text(tmp, stdout), 'stderr': _text(tmp, stderr),
            # (a rejected build leaves any earlier program in place: only a successful build's files count)
            'files': {path.name: made(path, tmp, native(arguments)) for path in files} if status == 0 else {}}


def outputs(target):
    """The files a build to `target` made (a Windows build adds .exe and .pdb)."""
    target = Path(target)
    return sorted(p for p in target.parent.glob(target.name + '*')
                  if p.is_file() and p.suffix not in ('.dewy', '.jo'))
