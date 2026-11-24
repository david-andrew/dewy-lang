"""Run golden-file language cases from tests/cases/<area>/<name>.dewy.

    python3 -m tools.core cases [-k WORDS] [--quick] [--update] [-n N]

A case passes when, in each of its modes, it exits with the expected code and
prints exactly `<name>.out` (missing means no output). A case with `<name>.err`
must fail to compile with matching diagnostics, or with an `exit:` header must
fail at run time with matching output. See tests/cases/README.md.

Ordinary cases of one mode compile together as modules of a single program and
run in one process; panicking cases share one build and run once each. A batch
that fails is split, and a failure that only reproduces in the combined program
is reported for all of its cases. Output outside every case's markers (a module's
top-level code runs before the batch's main) splits the batch until the case
printing it runs alone, as it would unbatched.

Quick (`# quick`, pytest's core_quick) is a smoke suite: one or two per subsystem.
Exhaustive variants, slow builds, determinism loops beyond one smoke case and
dogfood programs belong in the full suite.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import difflib
import json
import os
import re
import selectors
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import weakref
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

from tools import scratch as scratch_space
from tools.headless import headless

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / 'tests' / 'cases'
MODES = ('native', 'native-release', 'web', 'web-release')
HEADER_KEYS = ('exit', 'modes', 'args', 'stdin', 'quick')
BATCH_SIZE = 96
# Panicking and direct-exit cases share one build and run once each. Native
# starts are cheap and web runs reuse one persistent Node worker with a cached
# WebAssembly.Module.
PANIC_BATCH_SIZE = {'native': 32, 'web': 32}
MARK = '@@dewy-case@@'
BUILD_TIMEOUT = 120
RUN_TIMEOUT = 10

# Persistent per-worker Node runner: executes generated `.cjs` web runners in
# isolated vm contexts while caching the compiled WebAssembly.Module across
# `DEWY_CASE` runs of the same panic batch.
NODE_WORKER_JS = r"""
"use strict";
const fs = require("fs");
const vm = require("vm");
const readline = require("readline");
const EXIT_SENTINEL = Symbol("exit");
const startDir = process.cwd();
const cache = new Map();
const MAX_CACHE = 4;

function loadEntry(scriptPath) {
  const st = fs.statSync(scriptPath);
  const key = scriptPath + ":" + st.mtimeMs + ":" + st.size;
  let entry = cache.get(key);
  if (entry) {
    cache.delete(key);
    cache.set(key, entry);
    return entry;
  }
  const code = fs.readFileSync(scriptPath, "utf8");
  entry = { script: new vm.Script(code, { filename: scriptPath }), mod: null };
  cache.set(key, entry);
  if (cache.size > MAX_CACHE) cache.delete(cache.keys().next().value);
  return entry;
}

const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
rl.on("line", (line) => {
  if (!line) return;
  const req = JSON.parse(line);
  const out = [];
  const err = [];
  let code = 0;
  try {
    process.chdir(req.cwd);
    const entry = loadEntry(req.script);
    const shimProcess = {
      argv: [process.execPath, req.script, ...req.args],
      env: req.env,
      exitCode: 0,
      cwd: () => req.cwd,
      stdout: { write(chunk) { out.push(typeof chunk === "string" ? chunk : String(chunk)); return true; } },
      stderr: { write(chunk) { err.push(typeof chunk === "string" ? chunk : String(chunk)); return true; } },
      exit(c) { shimProcess.exitCode = c === undefined ? 0 : c; throw EXIT_SENTINEL; },
    };
    const fmt = (xs) => xs.map((x) => (typeof x === "string" ? x : String(x))).join(" ") + "\n";
    const shimConsole = {
      log: (...xs) => out.push(fmt(xs)),
      error: (...xs) => err.push(fmt(xs)),
      warn: (...xs) => err.push(fmt(xs)),
    };
    function CachedModule(bytes) {
      if (!entry.mod) entry.mod = new WebAssembly.Module(bytes);
      return entry.mod;
    }
    CachedModule.customSections = WebAssembly.Module.customSections;
    CachedModule.exports = WebAssembly.Module.exports;
    CachedModule.imports = WebAssembly.Module.imports;
    const shimWasm = Object.assign({}, WebAssembly, {
      Module: CachedModule,
      Instance: WebAssembly.Instance,
      Memory: WebAssembly.Memory,
      Table: WebAssembly.Table,
      Global: WebAssembly.Global,
      CompileError: WebAssembly.CompileError,
      LinkError: WebAssembly.LinkError,
      RuntimeError: WebAssembly.RuntimeError,
      instantiate: WebAssembly.instantiate,
      validate: WebAssembly.validate,
    });
    const sandbox = {
      Buffer,
      TextDecoder,
      TextEncoder,
      URL,
      URLSearchParams,
      atob,
      btoa,
      crypto,
      performance,
      structuredClone,
      queueMicrotask,
      console: shimConsole,
      process: shimProcess,
      WebAssembly: shimWasm,
      setTimeout,
      clearTimeout,
      setInterval,
      clearInterval,
    };
    try {
      entry.script.runInNewContext(sandbox);
    } catch (e) {
      if (e !== EXIT_SENTINEL) {
        err.push((e && e.stack ? e.stack : String(e)) + "\n");
        shimProcess.exitCode = 101;
      }
    }
    code = Number(shimProcess.exitCode || 0);
  } catch (e) {
    err.push((e && e.stack ? e.stack : String(e)) + "\n");
    code = 101;
  } finally {
    try { process.chdir(startDir); } catch (_) {}
  }
  process.stdout.write(JSON.stringify({ code, stdout: out.join(""), stderr: err.join("") }) + "\n");
});
"""


class _NodeWorker:
    """One persistent Node.js subprocess dedicated to a single worker thread."""

    def __init__(self, node: str, env: dict):
        self.node = node
        self.env = env
        self.proc: subprocess.Popen | None = None

    def _start(self):
        self.proc = subprocess.Popen(
            [self.node, '-e', NODE_WORKER_JS],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=self.env, bufsize=0,
        )

    def close(self):
        proc, self.proc = self.proc, None
        if proc is None:
            return
        try:
            if proc.stdin:
                proc.stdin.close()
        except OSError:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            try:
                proc.kill()
                proc.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                pass
        for stream in (proc.stdout, proc.stderr):
            if stream:
                try:
                    stream.close()
                except OSError:
                    pass

    def run(self, script: str, args: tuple[str, ...], cwd: str, env: dict, timeout: float):
        if self.proc is None or self.proc.poll() is not None:
            self.close()
            self._start()
        proc = self.proc
        assert proc is not None and proc.stdin is not None and proc.stdout is not None
        payload = json.dumps({'script': script, 'args': list(args), 'cwd': cwd, 'env': env}) + '\n'
        try:
            proc.stdin.write(payload.encode('utf-8'))
            proc.stdin.flush()
        except OSError:
            self.close()
            return None
        fd = proc.stdout.fileno()
        buf = bytearray()
        deadline = time.monotonic() + timeout
        selector = selectors.DefaultSelector()
        try:
            selector.register(fd, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self.close()
                    return 'timeout', '', ''
                if not selector.select(remaining):
                    self.close()
                    return 'timeout', '', ''
                chunk = os.read(fd, 65536)
                if not chunk:
                    self.close()
                    return None
                buf.extend(chunk)
                nl = buf.find(b'\n')
                if nl >= 0:
                    reply = json.loads(buf[:nl].decode('utf-8', 'replace'))
                    return int(reply['code']), reply['stdout'], reply['stderr']
        finally:
            selector.close()


def _close_workers(workers: list[_NodeWorker]):
    for worker in workers:
        worker.close()


class CaseError(ValueError):
    pass


@dataclass
class Case:
    name: str
    path: Path
    modes: tuple[str, ...] = MODES
    exit: int | None = None
    args: tuple[str, ...] = ()
    stdin: bytes | None = None
    quick: bool = False
    patterns: list[str] | None = None

    @property
    def out_path(self) -> Path:
        return self.path.with_suffix('.out')

    @property
    def expected(self) -> str:
        return self.out_path.read_bytes().decode() if self.out_path.exists() else ''

    @property
    def kind(self) -> str:
        if self.patterns is None:
            return 'run'
        return 'reject' if self.exit is None else 'panic'


def unescape(text: str) -> str:
    table = {'n': '\n', 't': '\t', 'r': '\r', '0': '\0', '\\': '\\'}
    return re.sub(r'\\(.)', lambda m: table.get(m[1], m[0]), text)


def parse(path: Path, root: Path = CASES) -> Case:
    case = Case(path.relative_to(root).with_suffix('').as_posix(), path)
    for line in path.read_text().splitlines():
        if not line.startswith('#'):
            break
        match = re.fullmatch(r'#\s*([a-z_]+)\s*(?::\s*(.*?))?\s*', line)
        if match is None or (match[2] is None and match[1] != 'quick'):
            continue  # an ordinary comment
        key, value = match[1], match[2]
        if key not in HEADER_KEYS:
            raise CaseError(f'{path}: unknown header key {key!r} (known: {", ".join(HEADER_KEYS)})')
        if key == 'exit':
            case.exit = int(value)
        elif key == 'modes':
            case.modes = tuple(value.split())
            unknown = set(case.modes) - set(MODES)
            if unknown or not case.modes:
                raise CaseError(f'{path}: modes must be among {" ".join(MODES)}')
        elif key == 'args':
            case.args = tuple(shlex.split(value))
        elif key == 'stdin':
            case.stdin = unescape(value).encode()
        else:
            case.quick = True
    error = path.with_suffix('.err')
    if error.exists():
        case.patterns = [line for line in error.read_text().splitlines() if line.strip()]
        if not case.patterns:
            raise CaseError(f'{error}: empty diagnostic expectation')
    elif case.exit is None:
        case.exit = 0
    if case.kind == 'reject' and case.out_path.exists():
        raise CaseError(f'{path}: a case that must not compile has no output to compare')
    return case


def keyword_filter(expression: str):
    """A pytest-style -k expression: words, and/or/not and parentheses."""
    tokens = re.findall(r'\(|\)|[^\s()]+', expression)
    if not tokens:
        return lambda name: True

    def predicate(name: str) -> bool:
        lowered = name.lower()
        code = []
        for token in tokens:
            if token in ('(', ')', 'and', 'or', 'not'):
                code.append(token)
            else:
                code.append(str(token.lower() in lowered))
        return eval(' '.join(code), {'__builtins__': {}})

    try:
        predicate('')
    except SyntaxError:
        raise CaseError(f'invalid -k expression: {expression!r}') from None
    return predicate


def discover(root: Path = CASES, keyword: str = '', quick: bool = False) -> list[Case]:
    selected = keyword_filter(keyword)
    cases = [parse(path, root) for path in sorted(root.rglob('*.dewy'))]
    return [case for case in cases if selected(case.name) and (case.quick or not quick)]


def match_patterns(patterns: list[str], text: str) -> list[str]:
    missing = []
    for pattern in patterns:
        if len(pattern) > 1 and pattern.startswith('/') and pattern.endswith('/'):
            found = re.search(pattern[1:-1], text, re.MULTILINE) is not None
        else:
            found = pattern in text
        if not found:
            missing.append(pattern)
    return missing


class Scripts(HTMLParser):
    """Extract the generated web runner, which also supports Node execution."""

    def __init__(self):
        super().__init__()
        self.inside = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.inside = True

    def handle_endtag(self, tag):
        if tag == 'script':
            self.inside = False

    def handle_data(self, data):
        if self.inside:
            self.parts.append(data)


@dataclass
class Outcome:
    case: Case
    mode: str
    ok: bool
    stdout: str | None = None
    message: str = ''
    stdout_only: bool = False  # the only problem is a stdout difference


@dataclass
class Runner:
    compiler: Path
    scratch: Path
    env: dict = field(default_factory=dict)
    node: str | None = None
    builds: int = 0
    runs: int = 0
    # Case path -> 'value' or 'void', once a build has settled how to call its main.
    settled: dict = field(default_factory=dict)
    # Cases a batch build rejected (the compiler reports one error per build, so each
    # costs a failed build to find): later batches and modes run them alone from the start.
    unbatchable: set = field(default_factory=set)
    # Cases whose main may panic (need `$runtime_checks` on the batch wrapper).
    needs_checked: set = field(default_factory=set)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _local: threading.local = field(default_factory=threading.local, repr=False)
    _node_workers: list = field(default_factory=list, repr=False)

    def __post_init__(self):
        workers = self._node_workers
        weakref.finalize(self, _close_workers, workers)

    def close(self):
        with self._lock:
            workers = list(self._node_workers)
            self._node_workers.clear()
        _close_workers(workers)

    def _node_worker(self) -> _NodeWorker:
        worker = getattr(self._local, 'node_worker', None)
        if worker is None:
            worker = _NodeWorker(self.node, self.env)
            self._local.node_worker = worker
            with self._lock:
                self._node_workers.append(worker)
        return worker

    def flags(self, mode: str) -> list[str]:
        flags = ['--release'] if mode.endswith('-release') else []
        return flags + (['--target', 'wasm32'] if mode.startswith('web') else [])

    def build(self, source: Path, output: Path, mode: str):
        self.builds += 1
        return subprocess.run([str(self.compiler), 'build', str(source), '-o', str(output), *self.flags(mode)],
                              cwd=output.parent, env=self.env, capture_output=True, text=True,
                              errors='replace', timeout=BUILD_TIMEOUT, check=False)

    def command(self, output: Path, mode: str) -> list[str]:
        if not mode.startswith('web'):
            if not output.exists() and output.with_suffix('.exe').exists():
                output = output.with_suffix('.exe')
            return [str(output)]
        scripts = Scripts()
        scripts.feed(output.with_suffix('.html').read_text())
        runner = output.with_suffix('.cjs')
        runner.write_text('const dewyArgs = process.argv.slice(1);\n' + '\n'.join(scripts.parts))
        return [self.node, str(runner)]

    def execute(self, command: list[str], args=(), stdin: bytes | None = None,
                timeout: float = RUN_TIMEOUT, select: int | None = None) -> tuple[int | str, str, str]:
        self.runs += 1
        env = self.env if select is None else {**self.env, 'DEWY_CASE': str(select)}
        if self.node and stdin is None and len(command) == 2 and command[0] == self.node:
            with scratch_space.run_dir('case', Path(command[-1]).parent) as cwd:
                result = self._node_worker().run(command[1], tuple(args), str(cwd), env, timeout)
                if result is not None:
                    return result
        try:
            with scratch_space.run_dir('case', Path(command[-1]).parent) as cwd:
                ran = subprocess.run([*command, *args], cwd=cwd, env=env,
                                     input=stdin if stdin is not None else b'', capture_output=True,
                                     timeout=timeout, check=False)
        except subprocess.TimeoutExpired as expired:
            return 'timeout', (expired.stdout or b'').decode('utf-8', 'replace'), \
                (expired.stderr or b'').decode('utf-8', 'replace')
        # Decode without newline translation: cases check control characters.
        return ran.returncode, ran.stdout.decode('utf-8', 'replace'), ran.stderr.decode('utf-8', 'replace')

    def directory(self, label: str) -> Path:
        return Path(tempfile.mkdtemp(prefix=label + '-', dir=self.scratch))

    # Checking -----------------------------------------------------------------

    def judge(self, case: Case, mode: str, code, stdout: str, stderr: str = '') -> Outcome:
        problems = []
        expected = case.exit if case.exit is not None else 0
        if code != expected:
            problems.append(f'exit {code}, expected {expected}')
        stdout_only = not problems and stdout != case.expected
        if stdout != case.expected:
            diff = difflib.unified_diff(case.expected.splitlines(keepends=True), stdout.splitlines(keepends=True),
                                        f'{case.name}.out', 'stdout', n=2)
            problems.append('stdout differs:\n' + ''.join(line if line.endswith('\n') else line + '\n\\ no newline\n'
                                                          for line in diff).rstrip('\n'))
        if case.kind == 'panic':
            missing = match_patterns(case.patterns, stdout + stderr)
            if missing:
                stdout_only = False
                problems.append('missing diagnostic: ' + ', '.join(map(repr, missing)))
        if problems and stderr.strip():
            problems.append('stderr:\n' + tail(stderr))
        return Outcome(case, mode, not problems, stdout, '\n'.join(problems), stdout_only)

    # Units of work -------------------------------------------------------------

    def single(self, case: Case, mode: str) -> list[Outcome]:
        work = self.directory('single')
        output = work / 'program'
        built = self.build(case.path, output, mode)
        diagnostics = built.stdout + built.stderr
        if case.kind == 'reject':
            problems = []
            if built.returncode == 0:
                problems.append('compiled, but a diagnostic was expected')
            problems += [f'missing diagnostic: {p!r}' for p in match_patterns(case.patterns, diagnostics)]
            if built.returncode and os.path.normcase(str(case.path)) not in os.path.normcase(built.stderr):
                problems.append('the diagnostic does not name the source file')
            if output.exists() or output.with_suffix('.html').exists():
                problems.append('a failed build left an output behind')
            if problems:
                problems.append('compiler output:\n' + tail(diagnostics))
            return [Outcome(case, mode, not problems, None, '\n'.join(problems))]
        if built.returncode:
            return [Outcome(case, mode, False, None, 'build failed:\n' + tail(diagnostics))]
        code, stdout, stderr = self.execute(self.command(output, mode), case.args, case.stdin)
        return [self.judge(case, mode, code, stdout, stderr)]

    def build_batch(self, cases: list[Case], mode: str, *, select: bool):
        """Build cases as modules of one program; returns (command, cases, singles, failure).

        Each case is called in one of three forms: 'value' keeps main's result;
        'guess' calls through a void-typed handle, so a wrong guess fails to
        compile instead of dropping a result; 'void' is a direct call, used only
        once main is known to have no result. The ownership check rejecting the
        handle (owners need direct calls) runs after type checking, so it also
        shows the handle's type matched. Settled forms carry over to other
        batches and modes.
        """
        with self._lock:
            singles = [case for case in cases if case.path in self.unbatchable]
            cases = [case for case in cases if case.path not in self.unbatchable]
            sources = [case.path.read_text() for case in cases]
            forms = [self.settled.get(case.path) or initial_form(src) for case, src in zip(cases, sources)]
            checked = select or any(
                case.path in self.needs_checked or needs_runtime_checks(src)
                for case, src in zip(cases, sources)
            )
        while cases:
            work = self.directory('select' if select else 'batch')
            source, lines = batch_source(cases, forms, select, checked=checked)
            (work / 'batch.dewy').write_text(source)
            output = work / 'batch'
            built = self.build(work / 'batch.dewy', output, mode)
            if built.returncode == 0:
                with self._lock:
                    for case, form in zip(cases, forms):
                        self.settled[case.path] = 'value' if form == 'value' else 'void'
                return self.command(output, mode), cases, singles, None
            located = locate_error(built.stderr, work, cases, lines)
            if located is None:
                return None, cases, singles, f'batch build failed in {work}:\n' + tail(built.stdout + built.stderr)
            index, message, ours = located
            if ours and not checked and 'may panic' in message:
                with self._lock:
                    self.needs_checked.add(cases[index].path)
                checked = True
                continue
            if ours and forms[index] == 'guess' and (
                'this expresses' in message or 'this gives nothing' in message
                or 'type mismatch' in message or '`:>void`' in message
                or 'owners require direct calls' in message
            ):
                forms[index] = 'void' if 'owners require direct calls' in message else 'value'
                with self._lock:
                    self.settled[cases[index].path] = forms[index]
            elif ours and forms[index] == 'value' and 'no type (void)' in message:
                forms[index] = 'void'
                with self._lock:
                    self.settled[cases[index].path] = 'void'
            else:
                with self._lock:
                    self.unbatchable.add(cases[index].path)
                singles.append(cases.pop(index))
                forms.pop(index)
                continue
        return None, cases, singles, None

    def value_batch(self, cases: list[Case], mode: str) -> list[Outcome]:
        command, cases, singles, failure = self.build_batch(cases, mode, select=False)
        outcomes = [outcome for case in singles for outcome in self.single(case, mode)]
        if failure:
            return outcomes + self.split(cases, mode, failure)
        if not cases:
            return outcomes
        code, stdout, stderr = self.execute(command, timeout=RUN_TIMEOUT * 6)
        if code == 'timeout':
            # No golden expects a timeout. Retrying its current case alone can
            # hide a deadlock that requires the combined program's imports.
            return outcomes + [Outcome(case, mode, False, None,
                               'batch timed out:\n' + tail(stdout + stderr)) for case in cases]
        finished, started, stray = parse_batch(stdout)
        if stray:
            return outcomes + self.isolate(cases, mode, self.value_batch)
        for index, (output, result) in finished.items():
            outcomes.append(self.judge(cases[index], mode, int(result) % 256, output))
        if len(finished) == len(cases):
            if code == 0:
                return outcomes
            # Every case returned, but the program failed afterwards.
            return outcomes[:len(outcomes) - len(cases)] + self.split(
                cases, mode, f'batch exited {code} after all cases returned:\n' + tail(stdout + stderr))
        # The case that started without finishing ended the process (a panic or
        # exit is legitimate for a case); run it alone and resume after it.
        if started is None or started in finished:
            return outcomes + self.split([c for i, c in enumerate(cases) if i not in finished], mode,
                                         f'batch exited {code} without a case result:\n' + tail(stdout + stderr))
        outcomes += self.single(cases[started], mode)
        rest = [c for i, c in enumerate(cases) if i > started and i not in finished]
        return outcomes + (self.value_batch(rest, mode) if rest else [])

    def split(self, cases: list[Case], mode: str, failure: str) -> list[Outcome]:
        if len(cases) == 1:
            return self.single(cases[0], mode)
        middle = len(cases) // 2
        outcomes = self.value_batch(cases[:middle], mode) + self.value_batch(cases[middle:], mode)
        # A failure that disappears when split must never pass the gate.
        if all(outcome.ok for outcome in outcomes):
            return [Outcome(case, mode, False, None, 'fails only when combined with its batch: ' + failure)
                    for case in cases]
        return outcomes

    def isolate(self, cases: list[Case], mode: str, batch) -> list[Outcome]:
        """Output no case's markers hold: halve the batch until its printer runs alone."""
        if len(cases) == 1:
            return self.single(cases[0], mode)
        middle = len(cases) // 2
        return batch(cases[:middle], mode) + batch(cases[middle:], mode)

    def panic_batch(self, cases: list[Case], mode: str) -> list[Outcome]:
        command, cases, singles, failure = self.build_batch(cases, mode, select=True)
        outcomes = [outcome for case in singles for outcome in self.single(case, mode)]
        if failure:
            return outcomes + [outcome for case in cases for outcome in self.single(case, mode)]
        judged = []
        for index, case in enumerate(cases):
            code, stdout, stderr = self.execute(command, select=index)
            # (every run runs every module's top-level code before the selected case's marker)
            before, marked, stdout = stdout.partition(f'{MARK}B{index}\n')
            if before or not marked:
                return outcomes + self.isolate(cases, mode, self.panic_batch)
            judged.append(self.judge(case, mode, code, stdout, stderr))
        return outcomes + judged


MAIN = re.compile(r'^main\s*=\s*(?:<[^>]*>\s*)?\(\s*\)\s*(?::>\s*([\w<>]+))?\s*=>\s*(\S)', re.MULTILINE)


def returns_void(source: str) -> bool:
    """Guess whether main has no result; the batch verifies the guess."""
    match = MAIN.search(source)
    if match is None:
        return False
    if match[1]:
        return match[1] == 'void'
    if match[2] != '{':
        return bool(re.match(r'(printl?\b|panic\b)', source[match.start(2):]))
    depth, end = 0, len(source)
    for position in range(match.start(2), len(source)):
        depth += {'{': 1, '}': -1}.get(source[position], 0)
        if depth == 0:
            end = position
            break
    body = source[match.end(2):end]
    # A value comes from `return <value>` or a trailing literal; anything else
    # (a nested function's return, say) costs one rebuild when misjudged.
    return re.search(r'\breturn[ \t]+[^\s}]', body) is None and \
        re.search(r'(^|\s)-?\d+\s*$', body) is None


# A case whose result is an exit code runs as `main=()=>exit(run())`; batches
# call the function itself and keep its result. A pure block wrapper is the
# same entry: running its exit would invoke process-wide finalizers mid-batch.
ENTRY = re.compile(r'^main\s*=\s*\(\s*\)\s*(?::>\s*void\s*)?=>\s*(?P<brace>\{)?\s*'
                   r'exit\((?P<entry>\w+)\(\)\)(?(brace)\s*\})\s*$', re.MULTILINE)


def entry_name(source: str) -> str:
    match = ENTRY.search(source)
    return match['entry'] if match else 'main'


MAIN_HEADER = re.compile(
    r'^(?:(?:let|const)\s+)?main\s*=\s*(?:<[^>]*>\s*)?\(\s*\)\s*(?::>\s*([^=\n]+?))?\s*=>\s*(\S)',
    re.MULTILINE,
)
CALL_EXPR = re.compile(r'([A-Za-z_]\w*)\s*\(')


def _strip_nested_lambdas(body: str) -> str:
    """Remove `=> { ... }` nested function bodies so their `return` does not fool main's guess."""
    out = []
    pos = 0
    arrow = re.compile(r'=>\s*\{')
    while (match := arrow.search(body, pos)) is not None:
        out.append(body[pos:match.start()])
        depth = 0
        end = len(body)
        for i in range(match.end() - 1, len(body)):
            ch = body[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        pos = end
    out.append(body[pos:])
    return ''.join(out)


def initial_form(source: str) -> str:
    """Choose the initial call form for a batched case's entry point.

    An explicit `main=():>void=>` (even with effect clauses like `& no panics`)
    is already checked by the compiler to have no result, so call it directly.
    Pure exit wrappers (`main=()=>exit(run())`) call `run()`, which returns an
    exit code. Fallible bodies (`or_throw`) return a union value.
    """
    if entry_name(source) != 'main':
        return 'value'
    match = MAIN_HEADER.search(source)
    if match is None:
        return 'value'
    if match[1]:
        base = match[1].split('&', 1)[0].strip()
        return 'void' if base == 'void' else 'value'
    if match[2] != '{':
        tail_expr = source[match.start(2):]
        if re.match(r'(printl?\b|panic\b|exit\b|\$?(?:runtime_)?assert\b)', tail_expr):
            return 'guess'
        call = CALL_EXPR.match(tail_expr)
        if call and re.search(rf'^(?:(?:let|const)\s+)?{re.escape(call[1])}\s*=\s*[^\n]*:>\s*void\b', source, re.MULTILINE):
            return 'guess'
        return 'value'
    depth, end = 0, len(source)
    for position in range(match.start(2), len(source)):
        depth += {'{': 1, '}': -1}.get(source[position], 0)
        if depth == 0:
            end = position
            break
    body = _strip_nested_lambdas(source[match.end(2):end])
    if re.search(r'\bor_throw\b', body) is not None:
        return 'value'
    if re.search(r'\breturn[ \t]+[^\s}]', body) is None and re.search(r'(^|\s)-?\d+\s*$', body) is None:
        return 'guess'
    return 'value'


def batch_source(cases: list[Case], forms: list[str], select: bool, *, checked: bool = False) -> tuple[str, dict[int, int]]:
    # Directives are module-local: `$runtime_checks` on the wrapper lets it call
    # cases whose own modules legitimately opt into runtime checks or panics,
    # without relaxing any imported case module's checking. Strict cases stay in
    # strict wrappers (`checked=False`).
    lines = ['$runtime_checks'] if (checked or select) else []
    owners: dict[int, int] = {}
    for i, case in enumerate(cases):
        lines.append(f'from p"{case.path.as_posix()}" import ({entry_name(case.path.read_text())} as case_{i})')
        owners[len(lines)] = i
    # A 'guess' case uses a direct-call `:>void` wrapper instead of taking a
    # `@case_i` handle: the compiler still rejects non-void results (never
    # silently dropping an exit code), and owned values work on the first try.
    for i, form in enumerate(forms):
        if form == 'guess':
            lines.append(f'v_{i}=():>void=>case_{i}()')
            owners[len(lines)] = i
    if select:
        # The selector comes from the environment so each case sees its own
        # arguments, exactly as when it runs alone.
        lines.append('main=():>void=>{')
        lines.append('let selector=env("DEWY_CASE") ?? ""')
    else:
        lines.append('main=():>void=>{')
    for i, form in enumerate(forms):
        owners[len(lines) + 1] = i
        void = {'guess': f'v_{i}()', 'void': f'case_{i}()'}.get(form)
        if select:
            call = f'{void} return' if void else f'let r_{i}=case_{i}() exit(r_{i})'
            lines.append(f'if selector =? "{i}" {{printl"{MARK}B{i}" {call}}}')
        else:
            # (buffered text is written out at each marker, so a case's raw writes to standard
            # output, a `syscall(1 ...)`, land between its own markers, not a neighbour's)
            lines.append(f'printl"{MARK}B{i}" flush_output()')
            owners[len(lines) + 1] = i
            if void:
                lines.append(f'{void} printl"{MARK}E{i}:0" flush_output()')
            else:
                lines.append(f'let r_{i}=case_{i}() printl"{MARK}E{i}:{{r_{i}}}" flush_output()')
    if select:
        lines.append('panic("invalid case selector")')
    lines.append('}')
    return '\n'.join(lines) + '\n', owners


ERROR = re.compile(r'^(.+?):(\d+):\d+: error: (.*)$', re.MULTILINE)


def locate_error(stderr: str, work: Path, cases: list[Case], owners: dict[int, int]):
    """Attribute the first build error to one case: (index, message, in-the-batch-file) or None."""
    match = ERROR.search(stderr)
    if match is None:
        return None
    path = Path(match[1])
    path = (path if path.is_absolute() else work / path).resolve()
    if path == (work / 'batch.dewy').resolve():
        index = owners.get(int(match[2]))
        return None if index is None else (index, match[3], True)
    for index, case in enumerate(cases):
        if path == case.path.resolve():
            return index, match[3], False
    return None


def parse_batch(stdout: str) -> tuple[dict[int, tuple[str, str]], int | None, bool]:
    """Each finished case's output and result, the last case started, and whether any
    output lies outside every case's markers (a module's top-level code, say)."""
    finished, started, position, stray = {}, None, 0, False
    begin = re.compile(re.escape(MARK) + r'B(\d+)\n')
    while (opened := begin.search(stdout, position)) is not None:
        stray = stray or opened.start() > position
        index = int(opened[1])
        started = index
        closed = re.compile('^' + re.escape(MARK) + rf'E{index}:(-?\d+|void)\n', re.MULTILINE).search(stdout, opened.end())
        if closed is None:
            return finished, started, stray
        finished[index] = stdout[opened.end():closed.start()], ('0' if closed[1] == 'void' else closed[1])
        position = closed.end()
    return finished, started, stray or position < len(stdout)


def tail(text: str, lines: int = 25) -> str:
    rows = text.rstrip().splitlines()
    shown = rows[-lines:]
    return '\n'.join((['…'] if len(rows) > lines else []) + ['    ' + row for row in shown])


# A batch imports each case's main; top-level-only programs run alone. Allocation
# measurements need their own executable too: another module can enable dynamic
# policy capture for callbacks, or leave process-wide allocation state behind.
DEFINES_MAIN = re.compile(r'^(?:(?:let|const)\s+)?main\s*[:=]', re.MULTILINE)
MAIN_WITH_PARAMS = re.compile(r'^(?:(?:let|const)\s+)?main\s*=\s*(?:<[^>]*>\s*)?\([^)\s]', re.MULTILINE)
ALLOCATION_COUNTER = re.compile(r'\balloc_count\b')
RUNTIME_CHECKS_CASE = re.compile(
    r'\$runtime_checks\b|\$prototype\b|\$allow_panics\b|\$runtime_assert\b|\bpanic\s*\('
)
DIRECT_EXIT = re.compile(r'\bexit\s*\(')


def needs_runtime_checks(source: str) -> bool:
    return RUNTIME_CHECKS_CASE.search(source) is not None


def exits_process(source: str) -> bool:
    return entry_name(source) == 'main' and DIRECT_EXIT.search(source) is not None


def needs_own_process(case: Case) -> bool:
    source = case.path.read_text()
    return DEFINES_MAIN.search(source) is None or MAIN_WITH_PARAMS.search(source) is not None \
        or ALLOCATION_COUNTER.search(source) is not None


# unbatchable: $no_deadlocks unsound with lock_all address order vs source-order locks; remove when fixed
ISOLATED_BUG_CASES = frozenset({'no_deadlocks/certified_locks'})


def plan(cases: list[Case], node: bool) -> list[tuple[str, str, list[Case]]]:
    units = []
    sources = {c.path: c.path.read_text() for c in cases if c.kind != 'reject'}
    alone = {
        c.path for c in cases
        if c.args or c.stdin is not None or c.name in ISOLATED_BUG_CASES or (
            c.kind != 'reject' and (
                DEFINES_MAIN.search(sources[c.path]) is None
                or MAIN_WITH_PARAMS.search(sources[c.path]) is not None
                or ALLOCATION_COUNTER.search(sources[c.path]) is not None
            )
        )
    }
    direct_exit = {p for p, src in sources.items() if p not in alone and exits_process(src)}
    checked_paths = {p for p, src in sources.items() if p not in alone and needs_runtime_checks(src)}
    for mode in MODES:
        if mode.startswith('web') and not node:
            continue
        chosen = [case for case in cases if mode in case.modes]
        strict_batched = [c for c in chosen if c.kind == 'run' and c.path not in alone
                          and c.path not in direct_exit and c.path not in checked_paths]
        checked_batched = [c for c in chosen if c.kind == 'run' and c.path not in alone
                           and c.path not in direct_exit and c.path in checked_paths]
        selects = [c for c in chosen if c.path not in alone
                   and (c.kind == 'panic' or (c.kind == 'run' and c.path in direct_exit))]
        in_batch = {c.path for c in strict_batched} | {c.path for c in checked_batched} | {c.path for c in selects}
        for group in (strict_batched, checked_batched):
            for start in range(0, len(group), BATCH_SIZE):
                units.append(('value', mode, group[start:start + BATCH_SIZE]))
        size = PANIC_BATCH_SIZE[mode.split('-')[0]]
        for start in range(0, len(selects), size):
            units.append(('panic', mode, selects[start:start + size]))
        units += [('single', mode, [c]) for c in chosen if c.path not in in_batch]
    return units


def clean_environment() -> dict:
    """A child's environment: no DEWY_ settings and no display (tools/headless.py)."""
    return dict(headless({key: value for key, value in os.environ.items() if not key.startswith('DEWY_')}))


def run(compiler: Path, cases: list[Case], *, workers: int = 2, update: bool = False,
        explicit: bool = False, verbose: bool = True, root: Path = CASES) -> int:
    started = time.perf_counter()
    if not cases:
        print('cases: none selected', file=sys.stderr)
        return 0
    node = shutil.which('node')
    if node is None and any(m.startswith('web') for c in cases for m in c.modes):
        print('cases: Node is not available; skipping web modes', file=sys.stderr)
    scratch = Path(tempfile.mkdtemp(prefix='dewy-cases-'))
    runner = Runner(compiler, scratch, clean_environment(), node)
    units = plan(cases, node is not None)
    outcomes: list[Outcome] = []
    # Run native batches first so `settled` and `unbatchable` are populated before
    # native-release, web, and web-release batches build, avoiding duplicate retries.
    priming = [u for u in units if u[0] in ('value', 'panic') and u[1] == 'native']
    rest = [u for u in units if not (u[0] in ('value', 'panic') and u[1] == 'native')]
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            method = {'value': runner.value_batch, 'panic': runner.panic_batch,
                      'single': lambda cases, mode: runner.single(cases[0], mode)}
            for phase in (priming, rest):
                if not phase:
                    continue
                futures = [pool.submit(method[kind], unit, mode) for kind, mode, unit in phase]
                for future in concurrent.futures.as_completed(futures):
                    outcomes.extend(future.result())
    finally:
        runner.close()
    by_case: dict[str, list[Outcome]] = {}
    for outcome in outcomes:
        by_case.setdefault(outcome.case.name, []).append(outcome)
    failed = []
    updated = []
    for case in cases:
        results = by_case.get(case.name, [])
        if all(o.ok for o in results):
            continue
        if update and case.kind != 'reject' and recordable(results):
            output = next(o.stdout for o in results)
            if case.out_path.exists() or explicit:
                if output:
                    case.out_path.write_bytes(output.encode())
                elif case.out_path.exists():
                    case.out_path.unlink()
                updated.append(case.name)
                continue
            results = [Outcome(o.case, o.mode, False, o.stdout, o.message + '\n(new output: record it with '
                               f'--update -k {case.name})') for o in results]
        failed.append((case, [o for o in results if not o.ok]))
    for case, results in failed:
        messages: dict[str, list[str]] = {}
        for outcome in sorted(results, key=lambda o: MODES.index(o.mode)):
            messages.setdefault(outcome.message, []).append(outcome.mode)
        for message, modes in messages.items():
            print(f'FAIL {case.name} [{" ".join(modes)}] ({display(case.path)})')
            print('  ' + message.replace('\n', '\n  '))
    elapsed = time.perf_counter() - started
    runs = sum(len(v) for v in by_case.values())
    if updated:
        print(f'cases: updated {len(updated)} expected output(s): ' + ', '.join(updated[:10])
              + (' …' if len(updated) > 10 else ''))
    summary = (f'cases: {len(cases) - len(failed)} passed, {len(failed)} failed '
               f'({runs} case runs, {runner.builds} builds) in {elapsed:.1f} s')
    if verbose or failed:
        print(summary, flush=True)
    shutil.rmtree(scratch, ignore_errors=True)
    if failed:
        kept = None
        for case, results in failed:
            kept = scratch_space.record_failure(case.name, ''.join(
                f'[{o.mode}] {o.message}\n--- stdout\n{o.stdout or ""}\n' for o in results)).parent
        print(f'cases: failing outputs kept in {kept}')
        print('cases: rerun with python3 -m tools.core cases -k NAME', flush=True)
    return 1 if failed else 0


def display(path: Path) -> Path:
    return path.relative_to(ROOT) if path.is_relative_to(ROOT) else path


def recordable(results: list[Outcome]) -> bool:
    """Only stdout may differ, identically in every mode, for --update to record it."""
    outputs = {o.stdout for o in results}
    return None not in outputs and len(outputs) == 1 and all(o.ok or o.stdout_only for o in results)


def arguments(argv: list[str] | None = None):
    cli = argparse.ArgumentParser(prog='python3 -m tools.core cases', description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument('-k', dest='keyword', default='', metavar='WORDS',
                     help='select cases whose name matches (pytest-style and/or/not)')
    cli.add_argument('--quick', action='store_true', help='only cases marked "# quick"')
    cli.add_argument('--update', action='store_true',
                     help='record actual output in existing .out files (new ones need -k)')
    cli.add_argument('-n', dest='workers', type=int, default=None, help='parallel workers (default: up to 4)')
    cli.add_argument('--compiler', type=Path, help='use this compiler instead of the cached build')
    return cli.parse_args(argv)


def default_workers() -> int:
    return min(4, getattr(os, 'process_cpu_count', os.cpu_count)() or 1)


def main(argv: list[str] | None = None, compiler: Path | None = None) -> int:
    options = arguments(argv)
    compiler = options.compiler or compiler
    if compiler is None:
        print('cases: pass --compiler or run through python3 -m tools.core cases', file=sys.stderr)
        return 2
    try:
        cases = discover(keyword=options.keyword, quick=options.quick)
    except CaseError as error:
        print(f'cases: {error}', file=sys.stderr)
        return 2
    workers = options.workers if options.workers is not None else default_workers()
    return run(Path(compiler).resolve(), cases, workers=workers or 1, update=options.update,
               explicit=bool(options.keyword))


if __name__ == '__main__':
    raise SystemExit(main())
