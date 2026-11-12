"""The source-cost comparison must not include the checkout path."""
from tools.compiler import speed


def test_identical_source_trees_have_zero_source_cost(tmp_path, monkeypatch, capsys):
    base = tmp_path / 'base-with-a-longer-name'
    current = tmp_path / 'current'
    for tree in (base, current):
        (tree / 'compiler').mkdir(parents=True)
        (tree / 'compiler/main.jo').write_text('printl"same"\n')
    monkeypatch.setattr(speed, 'CACHE', tmp_path / 'cache')
    monkeypatch.setattr(speed, 'ROOT', current)
    seen = []

    def measure(_counter, _candidate, path, _flags, _notes):
        seen.append((path, open(path).read()))
        return len(path) + len(open(path).read())

    monkeypatch.setattr(speed, 'measure', measure)
    speed.source_row(None, speed.Toolchain('candidate', None, None),
                     speed.Toolchain('base', None, None, base), {'self-build': 999}, [], 1, [])
    assert seen[0] == seen[1]
    assert '+0.00%' in capsys.readouterr().out
