"""Check live compiler probes against recorded outputs, or capture replacements for review."""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests' / 'fixtures' / 'leaf_outputs'
MODES = ('expected', 'capture')
SHARED = '_shared'
SHARED_FIELDS = ('args', 'stdout', 'stderr', 'files')

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


def record(arguments, status, output):
    # (a test's own directory differs from run to run: an absolute path keeps its name only)
    names = (os.fsdecode(a) for a in arguments)
    return {'args': ['<tmp>/' + Path(a).name if os.path.isabs(a) else a for a in names],
            'status': status, 'stdout': output.decode(errors='surrogateescape')}


def without(directory, output):
    """The output with the test's own directory and the checkout (both differ between runs and machines)
    named <tmp> and <root>: as text, as a flattened file name and as a list of byte values."""
    named = ((directory, b'<tmp>'), (ROOT, b'<root>')) if directory is not None else ((ROOT, b'<root>'),)
    for path, name in ((os.fsencode(place), name) for place, name in named):
        for form in (path, path.replace(b'/', b'_'), ', '.join(map(str, path)).encode()):
            output = output.replace(form, name)
    return output


@lru_cache(maxsize=1)
def _shared(directory):
    path = directory / f'{SHARED}.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def _read(module):
    path = FIXTURES / f'{module}.json'
    tests = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    shared = _shared(FIXTURES)
    for runs in tests.values():
        for index, entry in enumerate(runs):
            if isinstance(entry, int):
                entry = shared[str(entry)]
            runs[index] = {key: shared[str(value)] if key in SHARED_FIELDS and isinstance(value, int) else value
                           for key, value in entry.items()}
    return tests


def _expected(module):
    if module not in _loaded:
        indexed = defaultdict(list)
        for test, runs in _read(module).items():
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


def check(arguments, status, output):
    """Hold this probe run to its recorded output (or record it, when capturing)."""
    check_entry(lambda: record(arguments, status, output))


def _compact(entry):
    # Omitted status is zero. Omitted output and file fields are empty.
    return {key: value for key, value in entry.items() if value or key == 'args'}


def check_entry(make):
    """Hold this run's entry (make() builds it) to its record, or record it when capturing."""
    module, test, ordinal = _current()
    got = _compact(make())
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


def _json(value):
    text = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    try:
        text.encode('utf-8')
    except UnicodeEncodeError:
        return json.dumps(value, separators=(',', ':'))
    return text


def _write(module, body):
    path = FIXTURES / f'{module}.json'
    if not body:
        path.unlink(missing_ok=True)
        return
    text = '{\n' + ',\n'.join(body) + '\n}\n'
    if not path.exists() or text != path.read_text(encoding='utf-8'):
        path.write_text(text, encoding='utf-8')


def _intern(values, ids):
    """Store repeated values when references take less space than repetition."""
    next_id = max(ids.values(), default=0) + 1
    pool = {}
    for value, count in sorted(Counter(values).items()):
        if (len(value) - 6) * (count - 1) > 20:
            if value not in ids:
                ids[value] = next_id
                next_id += 1
            pool[value] = ids[value]
    return pool


def _write_fixtures(modules):
    # Repeated diagnostics, runtime outcomes and complete runs are stored once,
    # in full. Existing IDs keep fixture diffs local to the changed test data.
    ids = {_json(value): int(key) for key, value in _shared(FIXTURES).items()}
    fields = _intern((_json(entry[field]) for tests in modules.values() for runs in tests.values()
                      for entry in runs for field in SHARED_FIELDS if field in entry), ids)
    packed = {
        module: {
            test: [_json({key: fields.get(_json(value), value) if key in SHARED_FIELDS else value
                          for key, value in entry.items()}) for entry in runs]
            for test, runs in tests.items()
        }
        for module, tests in modules.items()
    }
    entries = _intern((entry for tests in packed.values() for runs in tests.values() for entry in runs), ids)
    for module, tests in sorted(packed.items()):
        lines = []
        for test, runs in sorted(tests.items()):
            records = (str(entries[entry]) if entry in entries else entry for entry in runs)
            lines.append(f' {_json(test)}: [\n  ' + ',\n  '.join(records) + '\n ]')
        _write(module, lines)
    _write(SHARED, [f' "{number}": {value}' for value, number in
                    sorted((fields | entries).items(), key=lambda item: item[1])])
    _shared.cache_clear()


def merge(directory, *, replace=False):
    """Fold captured runs into the fixture files. A run captured twice must agree with itself."""
    found = defaultdict(lambda: defaultdict(dict))
    for path in sorted(Path(directory).glob('*.jsonl')):
        for line in path.read_text().splitlines():
            item = json.loads(line)
            runs = found[item['module']][item['test']]
            previous = runs.setdefault(item['ordinal'], item['entry'])
            assert previous == item['entry'], (item['module'], item['test'], item['ordinal'])
    FIXTURES.mkdir(parents=True, exist_ok=True)
    modules = {path.stem: {} if replace else _read(path.stem)
               for path in sorted(FIXTURES.glob('*.json')) if path.stem != SHARED}
    for module, tests in found.items():
        merged = modules.setdefault(module, {})
        for test, runs in tests.items():
            assert sorted(runs) == list(range(len(runs))), (module, test)
            merged[test] = [runs[i] for i in range(len(runs))]
    if found:
        _write_fixtures(modules)
    return sum(len(tests) for tests in found.values())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory')
    parser.add_argument('--replace', action='store_true', help='remove tests absent from a complete capture')
    args = parser.parse_args()
    print(f'{merge(args.directory, replace=args.replace)} tests recorded')
