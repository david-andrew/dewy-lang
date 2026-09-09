"""Native bootstrap output is compared with the hosted parser's actual trees."""
import json
import subprocess
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.parser import p0, t1, t2
from dewy.reporting import SrcFile
from udewy.cache import cache_layout
from udewy.frontend import EntryPointOptions, entry_point

REPO = Path(__file__).resolve().parents[2]
PARSER = REPO / 'dewy/bootstrap/parser'
FIXTURES = sorted((REPO / 'dewy/bootstrap/tests').glob('*.dewy'))


@pytest.fixture(scope='module')
def t1_binary(tmp_path_factory):
    folder = tmp_path_factory.mktemp('bootstrap-t1')
    path = folder / 'parser.udewy'
    path.write_text(codegen(SrcFile.from_path(PARSER / 't1.dewy')))
    assert entry_point(path, [], EntryPointOptions(compile_only=True)) == 0
    directory, name = cache_layout(path)
    return (directory / name).resolve()


def number_text(number):
    return f'{number.prefix}:{number.src}'


def payload(node):
    if isinstance(node, (t1.Identifier, t1.Keyword, t1.Metatag)):
        return node.name
    if isinstance(node, t1.Operator):
        return node.symbol
    if isinstance(node, (t1.String, str)):
        return node if isinstance(node, str) else node.content
    if isinstance(node, t1.Bool):
        return str(node.value).lower()
    if isinstance(node, t1.Integer):
        return number_text(node.value)
    if isinstance(node, t1.Real):
        fraction = number_text(node.fraction) if node.fraction else ''
        e = node.exponent
        exponent = (('+' if e.positive else '-') + ('p' if e.binary else 'e') + number_text(e.value)) if e else ''
        return '|'.join((number_text(node.whole), fraction, exponent))
    if isinstance(node, t1.Block):
        return f'{node.kind}:{node.base or ""}'
    if isinstance(node, t1.BasedString):
        return f'{node.base}:' + '|'.join(d.src for d in node.digits)
    return ''


def hosted_t1_dump(nodes, depth=0):
    rows = []
    for node in nodes:
        kind = 'StringChunk' if isinstance(node, str) else type(node).__name__
        loc = (None, None) if isinstance(node, str) else (node.loc.start, node.loc.stop)
        rows.append((depth, kind, *loc, payload(node)))
        if isinstance(node, (t1.Block, t1.ParametricEscape)):
            rows.extend(hosted_t1_dump(node.inner, depth + 1))
        elif isinstance(node, t1.IString):
            rows.extend(hosted_t1_dump(node.content, depth + 1))
    return rows


def read_rows(output):
    rows = []
    for line in output.rstrip("\n").split("\n") if output else []:
        depth, kind, start, stop, text = line.split('\t', 4)
        literal = json.loads(text, strict=False)
        loc = (None, None) if kind == 'StringChunk' else (int(start), int(stop))
        rows.append((int(depth), kind, *loc, literal))
    return rows


SOURCES = [
    '', 'a 1 true False $tag ;', '[1..3) {a (b)} <T> 0x[ff]',
    '1e10 1p10 1e+10 1.25 1.2p-3 0x1.0x8p10',
    '"a\\nb" r"\\n" "\\u00Af"', '"a{1 + 2}b" t"x${name}"',
    '"\\u{41}"', '$"END"textEND', '$r"END"\\nEND',
    '$t"END"${1}tailEND', '$"""last character', '$"""',
    '$t"""a${1}tail', '0x"01 #{comment}# af"',
]


@pytest.mark.parametrize('source', SOURCES)
def test_t1_parity(t1_binary, tmp_path, source):
    path = tmp_path / 'source.dewy'
    path.write_text(source)
    run = subprocess.run([t1_binary, path, '--dump'], capture_output=True, text=True, timeout=60, check=False)
    assert run.returncode == 0, run.stderr
    assert read_rows(run.stdout) == hosted_t1_dump(t1.tokenize(SrcFile(None, source)))


@pytest.mark.parametrize('path', FIXTURES)
def test_t1_fixtures(t1_binary, tmp_path, path):
    test_t1_parity(t1_binary, tmp_path, path.read_text())


@pytest.fixture(scope='module')
def pipeline_binary(tmp_path_factory):
    folder = tmp_path_factory.mktemp('bootstrap-parser')
    path = folder / 'parser.udewy'
    path.write_text(codegen(SrcFile.from_path(PARSER / 'parser.dewy')))
    assert entry_point(path, [], EntryPointOptions(compile_only=True)) == 0
    directory, name = cache_layout(path)
    return (directory / name).resolve()


@pytest.fixture(scope='module', params=['t2', 'p0'])
def parser_binary(request, pipeline_binary):
    return request.param, pipeline_binary


def tree_parts(node):
    if isinstance(node, (t2.QJuxtapose, t2.Juxtapose)):
        options = node.options if isinstance(node, t2.QJuxtapose) else [node]
        return 'Juxtapose', '|'.join(type(o).__name__ for o in options), []
    if isinstance(node, t2.InvertedComparisonOp):
        return type(node).__name__, node.op, []
    if isinstance(node, (t2.BroadcastOp, t2.CombinedAssignmentOp, t2.OpFn)):
        return type(node).__name__, '', [node.op]
    if isinstance(node, (t2.Directive, p0.AssertDirective)):
        data = f'{node.name}:{str(node.condition is not None).lower()}:{str(node.message is not None).lower()}'
        return type(node).__name__, data, [v for v in (node.condition, node.message) if v is not None]
    if isinstance(node, (t2.Flow, p0.Flow)):
        return 'Flow', '', [*node.arms, *([node.default] if node.default is not None else [])]
    if isinstance(node, t2.Chain):
        return 'Chain', '', node.items
    if isinstance(node, (t2.KeywordExpr, p0.KeywordExpr)):
        return 'KeywordExpr', '', node.parts
    if isinstance(node, (t1.Block, p0.Block)):
        return 'Block', f'{node.kind}:{node.base or ""}', node.inner
    if isinstance(node, (t1.ParametricEscape, p0.ParametricEscape)):
        return 'ParametricEscape', '', node.inner
    if isinstance(node, (t1.IString, p0.IString)):
        return 'IString', '', node.content
    if isinstance(node, p0.Atom):
        return 'Atom', '', [node.item]
    if isinstance(node, p0.BinOp):
        return 'BinOp', '', [node.op, node.left, node.right]
    if isinstance(node, (p0.Prefix, p0.Postfix)):
        return type(node).__name__, '', [node.op, node.item]
    if isinstance(node, p0.Flat):
        return 'Flat', '', [node.op, *node.items]
    if isinstance(node, p0.Ambiguous):
        return 'Ambiguous', '', node.candidates
    return ('StringChunk' if isinstance(node, str) else type(node).__name__), payload(node), []


def hosted_dump(nodes, depth=0):
    rows = []
    for node in nodes:
        kind, data, children = tree_parts(node)
        loc = (None, None) if isinstance(node, str) else (node.loc.start, node.loc.stop)
        rows.append((depth, kind, *loc, data))
        rows.extend(hosted_dump(children, depth + 1))
    return rows


def canonical_tree(rows):
    """Ambiguous alternatives are a set of trees; their enumeration order
    carries no preference. Every other child order and source span matters."""
    roots, stack = [], []
    for depth, *data in rows:
        node = (tuple(data), [])
        del stack[depth:]
        (stack[-1][1] if stack else roots).append(node)
        stack.append(node)

    def freeze(node):
        data, children = node
        children = [freeze(child) for child in children]
        if data[0] == 'Ambiguous':
            children.sort(key=repr)
        return data, tuple(children)
    return tuple(freeze(node) for node in roots)


EXPRESSIONS = [
    '', 'a', '1 + 2 * 3', '-a^b', 'a--b', 'f(x)', '2(x)', 'f(x)+y',
    'a,b,c', '[1..3)', 'x:T = 1', 'a .+ b', 'a += 1', '(+) (<? 3)',
    'not a in? b', 'a not in? b', '$ >? 3', 'type of [x:int64]',
    'if a b else if c d else e', 'loop i in 0.. { printl i }',
    'return\nx = 1', 'return;', 'break $outer', 'continue',
    'from p"a" import x, y', 'import p"a" as b',
    '$assert x >? 0, "positive"', '$fail "oops"', '$breakpoint',
    '"a{1+2}b"', '0x[ff]', 'a;b', '(a) (b)', 'x:y:z', 'f(x)^y', 'a(b)(c)', 'a(b)*c', 'a ?? b', 'a <=> b',
]


@pytest.mark.parametrize('source', EXPRESSIONS)
def test_parser_parity(parser_binary, tmp_path, source):
    stage, binary = parser_binary
    srcfile = SrcFile(None, source)
    # Deliberate syntax errors are covered separately; preserve hosted rejection.
    from dewy.reporting import ReportException
    try:
        expected = t2.postok(srcfile) if stage == 't2' else [p0.parse(srcfile)]
    except ReportException:
        expected = None
    path = tmp_path / 'source.dewy'
    path.write_text(source)
    run = subprocess.run([binary, path, '--stage', stage, '--dump'], capture_output=True, text=True, timeout=60, check=False)
    if expected is None:
        assert run.returncode != 0
    else:
        assert run.returncode == 0, run.stderr
        assert canonical_tree(read_rows(run.stdout)) == canonical_tree(hosted_dump(expected))


@pytest.mark.parametrize('path', FIXTURES)
def test_parser_fixtures(parser_binary, tmp_path, path):
    test_parser_parity(parser_binary, tmp_path, path.read_text())


@pytest.mark.parametrize('stage', ['t0', 't1', 't2', 'p0'])
def test_invocation(pipeline_binary, tmp_path, stage):
    path = tmp_path / 'source.dewy'
    path.write_text('x = 1 + 2')
    run = subprocess.run([pipeline_binary, path, '--stage', stage], capture_output=True, text=True, timeout=60, check=False)
    assert run.returncode == 0, run.stderr
    assert ('Block' in run.stdout) if stage == 'p0' else (f'{stage} tokens' in run.stderr)


@pytest.mark.parametrize('arguments', [['--help'], [], ['--stage', 'bad'], ['missing.dewy']])
def test_invocation_errors_and_help(pipeline_binary, arguments):
    run = subprocess.run([pipeline_binary, *arguments], capture_output=True, text=True, timeout=60, check=False)
    assert run.returncode == (0 if arguments == ['--help'] else 1)
    assert run.stdout or run.stderr


@pytest.mark.parametrize('path', [PARSER / f'{stage}.dewy' for stage in ('t0', 't1', 't2', 'p0')])
def test_parser_self_parity(parser_binary, tmp_path, path):
    test_parser_parity(parser_binary, tmp_path, path.read_text())


def test_unicode_spans_use_dewy_grapheme_positions(parser_binary, tmp_path):
    from dewy.semantic.unicode.graphemes import graphemes
    stage, binary = parser_binary
    source = '"e\u0301" "🇺🇸"\r\nx = 1'
    path = tmp_path / 'unicode.dewy'
    path.write_bytes(source.encode())
    run = subprocess.run([binary, path, '--stage', stage, '--dump'], capture_output=True, text=True, timeout=60, check=False)
    assert run.returncode == 0, run.stderr
    srcfile = SrcFile(None, source)
    expected = t2.postok(srcfile) if stage == 't2' else [p0.parse(srcfile)]
    offsets, position = {0: 0}, 0
    for index, grapheme in enumerate(graphemes(source), 1):
        position += len(grapheme)
        offsets[position] = index
    rows = [(depth, kind, offsets[start], offsets[stop], payload) for depth, kind, start, stop, payload in hosted_dump(expected)]
    assert canonical_tree(read_rows(run.stdout)) == canonical_tree(rows)
