"""Build live compiler probes and record language-server sessions."""
import json
import os

from tests import leaf_oracle
from tests.selfhost_lower_double import cached_driver, modules_for
from tests.test_core_editor import Client

CLI_DRIVER = '''use 'main.jo'
main = ():
    lower_test_cli()
'''
DRIVER = CLI_DRIVER
_default_modules_for = modules_for


def leaf_compilers(compiler, tmp_path, leaves, recorded=True):
    """Build the live probe. Existing two-session callers receive the same compiler twice,
    with one session recording the expected outcomes."""
    live_cli = DRIVER == CLI_DRIVER and modules_for is _default_modules_for
    modules = dict(modules_for(tmp_path / 'unused.dewy', tmp_path / 'unused', () if live_cli else leaves))
    modules['driver.jo'] = DRIVER
    binary = cached_driver(compiler, tmp_path, False, modules)
    if recorded:
        return leaf_oracle.recording(binary, tmp_path, DRIVER == CLI_DRIVER), binary
    return binary, None


class Recorder(Client):
    """Every message the server sends, in order."""

    def receive(self):
        message = super().receive()
        self.log.append(message)
        return message

    def __init__(self, compiler, root):
        self.log = []
        super().__init__(compiler, root)


def session(compiler, root, steps):
    """steps: (method, params) requests, ('notify', (method, params)) notifications and ('text', (uri,
    text, version)) edits; the server's messages in order. Lowering in the server's pauses is off: whether
    a pause is long enough depends on the machine's load, and so would the diagnostics it publishes."""
    os.environ['DEWY_LSP_NO_IDLE_LOWERING'] = '1'
    try:
        client = Recorder(compiler, root)
    finally:
        del os.environ['DEWY_LSP_NO_IDLE_LOWERING']
    try:
        for method, params in steps:
            if method == 'text':
                client.set_text(*params)
            elif method == 'notify':
                client.send(*params)
            else:
                # (an error reply is part of what the builds must agree on)
                client.serial += 1
                client.send(method, params, client.serial)
                while (message := client.receive()).get('id') != client.serial:
                    client.messages.append(message)
        client.request('shutdown', None)
    finally:
        client.process.kill()
        client.process.wait()
    transcript = json.dumps(client.log, sort_keys=True)
    if leaf_oracle.recorded(compiler):
        # (the language server's messages, its project directory named: tests/leaf_oracle.py. A
        # notification may come before or after a reply, or again, so the record holds each distinct
        # message once, sorted.)
        messages = json.dumps(sorted({json.dumps(m, sort_keys=True) for m in client.log}))
        leaf_oracle.check_entry(lambda: {'args': ['lsp'], 'status': 0, 'stdout': leaf_oracle.text_or_digest(
            leaf_oracle.without(root, messages.encode()))})
    return transcript
