"""Run one language-server session against a compiler built with a Dewy leaf and with its frozen twin."""
import json
import os

from tests.selfhost_lower_double import cached_driver, modules_for
from tests.test_core_editor import Client

CLI_DRIVER = '''use 'main.jo'
main = ():
    lower_test_cli()
'''
DRIVER = CLI_DRIVER
_default_modules_for = modules_for


def leaf_compilers(compiler, tmp_path, leaves):
    """The compiler built with the leaves, then with their twins."""
    built = []
    for extension in ('dewy', 'jo'):
        # Custom probes keep their exact graph. Ordinary live CLI builds share one
        # graph: its reachable modules never import a leaf's frozen .jo body.
        live = extension == 'dewy' and DRIVER == CLI_DRIVER and modules_for is _default_modules_for
        modules = dict(modules_for(tmp_path / 'unused.dewy', tmp_path / 'unused', () if live else leaves))
        if extension == 'jo':
            # (every edge to a leaf, from Jo and from Dewy, leads to its twin)
            for name, text in modules.items():
                for leaf in leaves:
                    if name != f'{leaf}.jo':
                        text = (text.replace(f"'{leaf}.dewy'", f"'{leaf}.jo'")
                                .replace(f'"{leaf}.dewy"', f'"{leaf}.jo"'))
                modules[name] = text
        modules['driver.jo'] = DRIVER
        built.append(cached_driver(compiler, tmp_path, False, modules))
    return built


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
    return json.dumps(client.log, sort_keys=True)
