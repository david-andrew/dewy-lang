"""Expected outputs for leaf probe drivers: the oracle that replaces their frozen twins.

A probe driver (tests/leaf_driver.py) runs one Dewy leaf and prints what it computed. Each run's
status and output are recorded in tests/fixtures/leaf_outputs/<test module>.json, keyed by the test
id and the run's position in that test. The records were captured while the leaf and its frozen
twin agreed, so they hold the twin's answers once the twin is gone.

--leaf-oracle selects the oracle:
  both     (default) the twin comparison, then the recorded output;
  expected the recorded output alone; no twin is built;
  twin     the twin comparison alone (the path the recorded outputs replace);
  capture  the twin comparison; each agreed output is written to --leaf-capture DIR
           (merge with python3 -m tests.leaf_oracle DIR).
A changed record is a changed expectation: review its diff like a test edit.
"""
import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests' / 'fixtures' / 'leaf_outputs'
TEXT_LIMIT = 1 << 15
MODES = ('both', 'expected', 'twin', 'capture')

mode = 'both'
capture_dir = None
_ordinals = defaultdict(int)
_loaded = {}


def configure(config):
    global mode, capture_dir
    mode = config.getoption('leaf_oracle')
    capture_dir = config.getoption('leaf_capture')
    if mode == 'capture' and not capture_dir:
        raise ValueError('--leaf-oracle=capture needs --leaf-capture DIR')


def builds_twin():
    return mode != 'expected'


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
    entry = {'args': ['<tmp>/' + Path(a).name if os.path.isabs(a) else a for a in names], 'status': status}
    try:
        text = output.decode()
    except UnicodeDecodeError:
        text = None
    if text is not None and len(output) <= TEXT_LIMIT:
        entry['stdout'] = text
    else:
        entry['sha256'] = hashlib.sha256(output).hexdigest()
        entry['bytes'] = len(output)
    return entry


def without(directory, output):
    """The output with the test's own directory and the checkout (both differ between runs and machines)
    named <tmp> and <root>: as text, as a flattened file name and as a list of byte values."""
    for path, name in ((os.fsencode(directory), b'<tmp>'), (os.fsencode(ROOT), b'<root>')):
        for form in (path, path.replace(b'/', b'_'), ', '.join(map(str, path)).encode()):
            output = output.replace(form, name)
    return output


def _expected(module):
    if module not in _loaded:
        path = FIXTURES / f'{module}.json'
        _loaded[module] = json.loads(path.read_text()) if path.exists() else {}
    return _loaded[module]


def check(arguments, status, output):
    """Hold this probe run to its recorded output (or record it, when capturing)."""
    module, test, ordinal = _current()
    if mode == 'twin':
        return
    got = record(arguments, status, output)
    if mode == 'capture':
        line = json.dumps({'module': module, 'test': test, 'ordinal': ordinal, 'entry': got})
        target = Path(capture_dir) / f'{os.environ.get("PYTEST_XDIST_WORKER", "main")}-{os.getpid()}.jsonl'
        with target.open('a') as stream:
            stream.write(line + '\n')
        return
    runs = _expected(module).get(test, [])
    assert ordinal < len(runs), (f'{module}::{test} run {ordinal}: no recorded output in '
                                 f'tests/fixtures/leaf_outputs/{module}.json')
    want = runs[ordinal]
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
        path.write_text(json.dumps(dict(sorted(merged.items())), indent=1, ensure_ascii=False) + '\n')
    return sum(len(tests) for tests in found.values())


if __name__ == '__main__':
    print(f'{merge(sys.argv[1])} tests recorded')
