"""Check live compiler probes against recorded outputs, or capture replacements for review."""
import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests' / 'fixtures' / 'leaf_outputs'
TEXT_LIMIT = 1 << 15
MODES = ('expected', 'capture')


def text_or_digest(data):
    """Text up to TEXT_LIMIT bytes, else the bytes' digest and size."""
    try:
        if len(data) <= TEXT_LIMIT:
            return data.decode()
    except UnicodeDecodeError:
        pass
    return {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}

mode = 'expected'
capture_dir = None
_ordinals = defaultdict(int)
_loaded = {}


def configure(config):
    global mode, capture_dir
    mode = config.getoption('leaf_oracle')
    capture_dir = config.getoption('leaf_capture')
    if mode == 'capture':
        if not capture_dir:
            raise ValueError('--leaf-oracle=capture needs --leaf-capture DIR')
        Path(capture_dir).mkdir(parents=True, exist_ok=True)


def extensions(pair=('dewy',)):
    """Select the live module from a probe's list of source variants."""
    return pair[:1]


def agree(outputs, arguments=(), status=0, directory=None):
    """Check the output of an inline probe against its record."""
    output, = outputs
    return check_value(output, arguments, status, directory)


def check_value(output, arguments=(), status=0, directory=None):
    # (structured output is recorded as its repr)
    data = output if isinstance(output, bytes) else (output if isinstance(output, str) else repr(output)).encode()
    check(arguments, status, data if directory is None else without(directory, data))
    return output


current = None  # (module stem, test name), set by tests/conftest.py for each test


def _current():
    """(module stem, test name, ordinal) of this run within the running test."""
    assert current is not None, 'a leaf probe ran outside a test'
    ordinal = _ordinals[current]
    _ordinals[current] += 1
    return (*current, ordinal)


def record(arguments, status, output, digest=False):
    # (a test's own directory differs from run to run: an absolute path keeps its name only)
    names = (os.fsdecode(a) for a in arguments)
    entry = {'args': ['<tmp>/' + Path(a).name if os.path.isabs(a) else a for a in names], 'status': status}
    try:
        text = output.decode()
    except UnicodeDecodeError:
        text = None
    if text is not None and len(output) <= TEXT_LIMIT and not digest:
        entry['stdout'] = text
    else:
        entry['sha256'] = hashlib.sha256(output).hexdigest()
        entry['bytes'] = len(output)
    return entry


def without(directory, output):
    """The output with the test's own directory and the checkout (both differ between runs and machines)
    named <tmp> and <root>: as text, as a flattened file name and as a list of byte values."""
    named = ((directory, b'<tmp>'), (ROOT, b'<root>')) if directory is not None else ((ROOT, b'<root>'),)
    for path, name in ((os.fsencode(place), name) for place, name in named):
        for form in (path, path.replace(b'/', b'_'), ', '.join(map(str, path)).encode()):
            output = output.replace(form, name)
    return output


def _expected(module):
    if module not in _loaded:
        path = FIXTURES / f'{module}.json'
        tests = json.loads(path.read_text()) if path.exists() else {}
        indexed = defaultdict(list)
        for test, runs in tests.items():
            for run in runs:
                indexed[test, tuple(run['args'])].append(run)
        _loaded[module] = indexed
    return _loaded[module]


_logs = []
_recording = set()


def recording(binary, tmp_path, cli=True):
    """A stand-in for binary that records each invocation (tests/leaf_record.py) for check_logs().
    cli: binary is the compiler's command line, which starts the interactive prompt bare."""
    stand_in = Path(tmp_path) / f'leaf-compiler-{len(_logs)}'
    log = stand_in.with_suffix('.jsonl')
    stand_in.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{ROOT / "tests/leaf_record.py"}" '
                        f'"{log}" "{binary}" "{tmp_path}" {int(cli)} "$0" "$@"\n')
    stand_in.chmod(0o755)
    _logs.append(log)
    _recording.add(str(stand_in))
    return stand_in


def recorded(binary):
    """Whether this compiler is a recording stand-in (its sessions are recorded by the caller)."""
    return str(binary) in _recording


def drop_logs():
    _logs.clear()


def check_logs():
    """Hold the invocations the stand-ins recorded in this test to their records."""
    logs = list(_logs)
    _logs.clear()
    for log in logs:
        for line in log.read_text().splitlines() if log.exists() else ():
            check_entry(lambda line=line: json.loads(line))


def check(arguments, status, output, digest=False):
    """Hold this probe run to its recorded output (or record it, when capturing). digest: record the
    output's hash alone (a test with thousands of runs keeps its records small)."""
    check_entry(lambda: record(arguments, status, output, digest))


def check_entry(make):
    """Hold this run's entry (make() builds it) to its record, or record it when capturing."""
    module, test, ordinal = _current()
    got = make()
    if mode == 'capture':
        line = json.dumps({'module': module, 'test': test, 'ordinal': ordinal, 'entry': got})
        target = Path(capture_dir) / f'{os.environ.get("PYTEST_XDIST_WORKER", "main")}-{os.getpid()}.jsonl'
        with target.open('a') as stream:
            stream.write(line + '\n')
        return
    # (a run is found by its arguments, in order among runs with the same arguments, so a test whose
    # inputs come from a directory keeps its records when a case is added beside them)
    key = tuple(got['args'])
    same = _ordinals[(module, test, key)]
    _ordinals[(module, test, key)] += 1
    runs = _expected(module).get((test, key), ())
    assert same < len(runs), (f'{module}::{test} run {ordinal} ({got["args"]}): no recorded output in '
                              f'tests/fixtures/leaf_outputs/{module}.json; record it with '
                              f'--leaf-oracle=capture --leaf-capture DIR, then python3 -m tests.leaf_oracle DIR')
    want = runs[same]
    assert got == want, f'{module}::{test} run {ordinal} differs from its recorded output:\n got {got}\nwant {want}'


def merge(directory):
    """Fold captured runs into the fixture files. A run captured twice must agree with itself."""
    found = defaultdict(lambda: defaultdict(dict))
    for path in sorted(Path(directory).glob('*.jsonl')):
        for line in path.read_text().splitlines():
            item = json.loads(line)
            runs = found[item['module']][item['test']]
            previous = runs.setdefault(item['ordinal'], item['entry'])
            assert previous == item['entry'], (item['module'], item['test'], item['ordinal'])
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for module, tests in sorted(found.items()):
        path = FIXTURES / f'{module}.json'
        merged = json.loads(path.read_text()) if path.exists() else {}
        for test, runs in tests.items():
            assert sorted(runs) == list(range(len(runs))), (module, test)
            merged[test] = [runs[i] for i in range(len(runs))]
        text = json.dumps(dict(sorted(merged.items())), indent=1, ensure_ascii=False)
        try:
            text.encode()
        except UnicodeEncodeError:  # (output that is not UTF-8 stays escaped)
            text = json.dumps(dict(sorted(merged.items())), indent=1)
        path.write_text(text + '\n')
    return sum(len(tests) for tests in found.values())


if __name__ == '__main__':
    print(f'{merge(sys.argv[1])} tests recorded')
