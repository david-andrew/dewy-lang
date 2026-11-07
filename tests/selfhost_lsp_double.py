"""Run one language-server session against a compiler built with a Dewy leaf and with its frozen twin."""
import json

from tests.selfhost_lower_double import cached_driver, modules_for
from tests.test_core_editor import Client

DRIVER = '''use 'main.jo'
main = ():
    lower_test_cli()
'''


def leaf_compilers(compiler, tmp_path, leaf):
    """The compiler built with the leaf, then with its twin."""
    built = []
    for extension in ('dewy', 'jo'):
        modules = dict(modules_for(tmp_path / 'unused.dewy', tmp_path / 'unused', leaf))
        if extension == 'jo':
            for name, text in modules.items():
                if name.endswith('.jo') and name != f'{leaf}.jo':
                    modules[name] = text.replace(f"'{leaf}.dewy'", f"'{leaf}.jo'")
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
    text, version)) edits; the server's messages in order."""
    client = Recorder(compiler, root)
    try:
        for method, params in steps:
            if method == 'text':
                client.set_text(*params)
            elif method == 'notify':
                client.send(*params)
            else:
                client.request(method, params)
        client.request('shutdown', None)
    finally:
        client.process.kill()
        client.process.wait()
    return json.dumps(client.log, sort_keys=True)
