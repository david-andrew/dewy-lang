"""The editor integration, end to end: drive CodeLLDB's debug adapter over DAP
exactly as Cursor/VS Code's Run and Debug pane does, with the launch
configuration checked into `.vscode/launch.json`, against a Dewy debug build.
Skipped where the CodeLLDB extension (Cursor, VS Code, or VSCodium) is not installed."""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from shutil import which

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.frontend import EntryPointOptions, entry_point

repo = Path(__file__).resolve().parents[2]

PROGRAM = '''let Hit = type of any & [length:uint64 name:string]
let scale:int64 = 3
let describe = (hits:array<Hit> label:string):>int64 => {
    let total:int64 = 0
    loop h in hits {
        total += (h.length transmute int64) * scale
        let maybe:int64|none = if total >? 10 total else none
        $breakpoint
    }
    return total
}
let main = ():>int64 => {
    let hits:array<Hit> = [Hit[length=3 name="a"] Hit[length=10 name="b"]]
    let r = describe(hits "run")
    return 42
}
'''


def _codelldb() -> tuple[Path, Path] | None:
    for extensions in (Path.home() / '.cursor' / 'extensions', Path.home() / '.vscode' / 'extensions', Path.home() / '.vscode-oss' / 'extensions'):
        for candidate in sorted(extensions.glob('vadimcn.vscode-lldb-*'), reverse=True):
            adapter = candidate / 'adapter' / 'codelldb'
            liblldb = candidate / 'lldb' / 'lib' / 'liblldb.so'
            if adapter.is_file() and liblldb.is_file():
                return adapter, liblldb
    return None


class _Session:
    """A minimal DAP client over the adapter's TCP port."""

    def __init__(self, adapter: Path, liblldb: Path) -> None:
        probe = socket.socket()
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
        probe.close()
        self.process = subprocess.Popen([str(adapter), '--liblldb', str(liblldb), '--port', str(port)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                self.socket = socket.create_connection(('127.0.0.1', port))
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError('codelldb did not start')
        self.stream = self.socket.makefile('rwb', buffering=0)
        self.seq = 0
        self.output: list[str] = []

    def send(self, command: str, arguments: dict | None = None) -> None:
        self.seq += 1
        body = json.dumps({'seq': self.seq, 'type': 'request', 'command': command, 'arguments': arguments or {}}).encode()
        self.stream.write(b'Content-Length: %d\r\n\r\n' % len(body) + body)

    def read(self) -> dict:
        headers = b''
        while not headers.endswith(b'\r\n\r\n'):
            headers += self.stream.read(1)
        length = int(headers.split(b':')[1])
        data = b''
        while len(data) < length:
            data += self.stream.read(length - len(data))
        return json.loads(data)

    def wait(self, *, command: str | None = None, event: str | None = None) -> dict:
        while True:
            message = self.read()
            if message['type'] == 'event' and message['event'] == 'output':
                self.output.append(message['body'].get('output', ''))
                continue
            if command is not None and message['type'] == 'response' and message['command'] == command:
                return message
            if event is not None and message['type'] == 'event' and message['event'] == event:
                return message

    def close(self) -> None:
        try:
            self.send('disconnect', {'terminateDebuggee': True})
            self.wait(command='disconnect')
        finally:
            self.process.kill()


def _launch_configuration(name: str, substitutions: dict[str, str]) -> dict:
    """A configuration of the repository's launch.json with its `${…}` variables substituted."""
    text = re.sub(r'^\s*//.*$', '', (repo / '.vscode' / 'launch.json').read_text(), flags=re.M)
    configuration = next(entry for entry in json.loads(text)['configurations'] if entry['name'] == name)

    def substitute(value):
        if isinstance(value, str):
            return re.sub(r'\$\{(\w+)\}', lambda match: substitutions[match.group(1)], value)
        if isinstance(value, list):
            return [substitute(item) for item in value]
        return value

    return {key: substitute(value) for key, value in configuration.items() if key != 'preLaunchTask'}


@pytest.mark.skipif(which('as') is None or which('ld') is None or _codelldb() is None, reason='needs the x86_64 toolchain and the CodeLLDB extension')
def test_the_editor_session_shows_dewy_frames_values_and_breakpoints(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    adapter, liblldb = _codelldb()   # type: ignore[misc]
    workspace = tmp_path
    (workspace / 'src').mkdir()
    source = workspace / 'src' / 'session.dewy'
    source.write_text(PROGRAM)
    # the pre-launch task: `dewy debug --build src/session.dewy` from the workspace folder
    monkeypatch.chdir(workspace)
    udewy_path = workspace / '__dewycache__' / 'src' / 'session.debug.udewy'
    udewy_path.parent.mkdir(parents=True)
    udewy_path.write_text(codegen(SrcFile.from_path(source), debug_values=True))
    assert entry_point(udewy_path, [], EntryPointOptions(compile_only=True)) == 0
    configuration = _launch_configuration('Dewy: debug current file (lldb)', {
        'workspaceFolder': str(workspace), 'relativeFileDirname': 'src', 'fileBasenameNoExtension': 'session',
    })
    configuration['initCommands'] = [command.replace(str(workspace) + '/tools', str(repo / 'tools')) for command in configuration['initCommands']]
    assert configuration['program'] == str(workspace / '__dewycache__' / 'src' / 'session.debug')
    assert Path(configuration['program']).is_file()

    session = _Session(adapter, liblldb)
    try:
        session.send('initialize', {'adapterID': 'lldb', 'linesStartAt1': True, 'columnsStartAt1': True, 'pathFormat': 'path'})
        session.wait(command='initialize')
        session.send('launch', configuration)
        session.wait(event='initialized')
        session.send('setBreakpoints', {'source': {'path': str(source)}, 'breakpoints': [{'line': 6}]})   # a gutter click on `total += …`
        breakpoints = session.wait(command='setBreakpoints')['body']['breakpoints']
        assert [(point['verified'], point['line']) for point in breakpoints] == [(True, 6)]
        session.send('configurationDone')
        assert session.wait(event='stopped')['body']['reason'] == 'breakpoint'
        session.send('threads')
        thread = session.wait(command='threads')['body']['threads'][0]['id']
        session.send('stackTrace', {'threadId': thread})
        frames = session.wait(command='stackTrace')['body']['stackFrames']
        assert [(frame['name'], frame['line']) for frame in frames[:2]] == [('describe', 6), ('__dewy_user_main', 14)]
        assert frames[0]['source']['name'] == 'session.dewy'
        session.send('scopes', {'frameId': frames[0]['id']})
        scopes = session.wait(command='scopes')['body']['scopes']
        locals_scope = next(scope for scope in scopes if scope['name'] == 'Local')
        session.send('variables', {'variablesReference': locals_scope['variablesReference']})
        shown = {variable['name']: (variable['value'], variable.get('type')) for variable in session.wait(command='variables')['body']['variables']}
        assert shown['hits'] == ('[Hit[length=3 name="a"] Hit[length=10 name="b"]]', 'array<Hit>')
        assert shown['label'] == ('"run"', 'string') and shown['maybe'] == ('none', 'int64 | none')
        assert shown['total'] == ('0', 'int64') and shown['h'] == ('Hit[length=3 name="a"]', 'Hit')
        session.send('evaluate', {'expression': 'h', 'frameId': frames[0]['id'], 'context': 'hover'})   # a hover
        assert session.wait(command='evaluate')['body']['result'] == 'Hit[length=3 name="a"]'
        session.send('next', {'threadId': thread})                                                   # step over
        session.wait(command='next')
        assert session.wait(event='stopped')['body']['reason'] == 'step'
        session.send('stackTrace', {'threadId': thread})
        assert session.wait(command='stackTrace')['body']['stackFrames'][0]['line'] == 7
        session.send('continue', {'threadId': thread})                                               # into the `$breakpoint`
        session.wait(command='continue')
        stop = session.wait(event='stopped')['body']
        assert 'SIGTRAP' in stop.get('description', '') or stop['reason'] == 'exception'
        session.send('stackTrace', {'threadId': thread})
        assert session.wait(command='stackTrace')['body']['stackFrames'][0]['line'] == 8
        console = ''.join(session.output)
        assert '── breakpoint at session.dewy:8 ──' in console and 'total = 9' in console                # the snapshot, in the Debug Console
    finally:
        session.close()


def _task_command(label: str, substitutions: dict[str, str]) -> list[str]:
    """A task of the repository's tasks.json as a command line, with its `${…}` variables substituted."""
    text = re.sub(r'^\s*//.*$', '', (repo / '.vscode' / 'tasks.json').read_text(), flags=re.M)
    tasks = json.loads(text)
    task = next(entry for entry in tasks['tasks'] if entry['label'] == label)
    inputs = {entry['id']: entry['default'] for entry in tasks.get('inputs', [])}

    def substitute(value: str) -> str:
        return re.sub(r'\$\{(?:input:)?(\w+)\}', lambda match: substitutions.get(match.group(1), inputs.get(match.group(1), match.group(0))), value)

    return [substitute(task['command']), *(substitute(argument) for argument in task['args'])]


@pytest.mark.skipif(which('as') is None or which('ld') is None or _codelldb() is None, reason='needs the x86_64 toolchain and the CodeLLDB extension')
def test_a_program_debugged_on_the_editors_file(tmp_path: Path) -> None:
    """`Dewy: debug a program on current file`: the build task's prompt defaults to
    the bootstrap tokenizer, which then runs on the file in the active editor."""
    adapter, liblldb = _codelldb()   # type: ignore[misc]
    tokenized = tmp_path / 'one_comment.dewy'
    tokenized.write_text('# just a comment\n')
    command = _task_command('dewy: build debug target', {'workspaceFolder': str(repo)})
    command[0] = sys.executable if command[0] == 'python' else command[0]
    assert command[-1] == 'dewy/bootstrap/parser/t0.dewy'                                 # the prompt's default
    built = subprocess.run(command, cwd=repo, capture_output=True, text=True, timeout=600, env={**os.environ, 'PYTHONPATH': str(repo)})
    assert built.returncode == 0, built.stderr
    configuration = _launch_configuration('Dewy: debug a program on current file (lldb)', {'workspaceFolder': str(repo), 'file': str(tokenized)})
    assert Path(configuration['program']).is_file() and configuration['args'] == [str(tokenized)]
    t0 = repo / 'dewy' / 'bootstrap' / 'parser' / 't0.dewy'
    line = next(number for number, text in enumerate(t0.read_text().splitlines(), 1) if text.strip().startswith('matches.sort('))
    session = _Session(adapter, liblldb)
    try:
        session.send('initialize', {'adapterID': 'lldb', 'linesStartAt1': True, 'columnsStartAt1': True, 'pathFormat': 'path'})
        session.wait(command='initialize')
        session.send('launch', configuration)
        session.wait(event='initialized')
        session.send('setBreakpoints', {'source': {'path': str(t0)}, 'breakpoints': [{'line': line}]})
        assert session.wait(command='setBreakpoints')['body']['breakpoints'][0]['verified']
        session.send('configurationDone')
        assert session.wait(event='stopped')['body']['reason'] == 'breakpoint'
        session.send('threads')
        thread = session.wait(command='threads')['body']['threads'][0]['id']
        session.send('stackTrace', {'threadId': thread})
        frames = session.wait(command='stackTrace')['body']['stackFrames']
        assert (frames[0]['name'], frames[0]['line']) == ('tokenize', line)
        session.send('scopes', {'frameId': frames[0]['id']})
        locals_scope = next(scope for scope in session.wait(command='scopes')['body']['scopes'] if scope['name'] == 'Local')
        session.send('variables', {'variablesReference': locals_scope['variablesReference']})
        shown = {variable['name']: variable['value'] for variable in session.wait(command='variables')['body']['variables']}
        assert shown['src'] == '"# just a comment\\n"'
        assert shown['matches'] == '[[length=17 token_cls=LineComment]]'
    finally:
        session.close()
