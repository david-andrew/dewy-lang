"""The VS Code TextMate grammar against today's Dewy surface.

A small TextMate interpreter (match, begin/end, captures, includes) tokenizes sample lines; the
grammar keeps to regular expressions that Python and Oniguruma read alike.
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GRAMMAR = ROOT / 'editors/vscode/syntaxes/dewy.tmLanguage.json'


class Grammar:
    def __init__(self, raw):
        self.repository = raw['repository']
        self.top = self.flatten(raw['patterns'])

    def flatten(self, patterns):
        out = []
        for rule in patterns:
            if 'include' in rule:
                target = rule['include']
                assert target.startswith('#'), target
                rule = self.repository[target[1:]]
            if 'match' in rule or 'begin' in rule:
                out.append(rule)
                for key in ('match', 'begin', 'end'):
                    if key in rule and key + '_re' not in rule:
                        rule[key + '_re'] = re.compile(rule[key])
            else:
                out.extend(self.flatten(rule['patterns']))
        return out

    @staticmethod
    def captured(line, match, scopes, captures):
        spans = [list(scopes) for _ in range(match.start(), match.end())]
        for group in sorted(captures, key=int):
            index = int(group)
            if match.start(index) < 0:
                continue
            for i in range(match.start(index), match.end(index)):
                spans[i - match.start()].append(captures[group]['name'])
        return [(line[match.start() + i], tuple(s)) for i, s in enumerate(spans)]

    def tokenize(self, text):
        """Lines of [(text, scopes)], each run of equally scoped characters one token."""
        stack = []          # (rule, scopes inside it)
        lines = []
        for line in text.split('\n'):
            chars = []
            pos = 0
            while pos <= len(line):
                scopes = stack[-1][1] if stack else ('source.dewy',)
                rules = self.flatten(stack[-1][0].get('patterns', [])) if stack else self.top
                best = None
                if stack:
                    end = stack[-1][0]['end_re'].search(line, pos)
                    if end:
                        best = (end.start(), 0, end, None)
                for order, rule in enumerate(rules, 1):
                    found = (rule.get('match_re') or rule['begin_re']).search(line, pos)
                    if found and (best is None or found.start() < best[0]):
                        best = (found.start(), order, found, rule)
                if best is None:
                    chars.extend((c, scopes) for c in line[pos:])
                    break
                start, _, found, rule = best
                chars.extend((c, scopes) for c in line[pos:start])
                if rule is None:
                    closing, inside = stack.pop()
                    outer = inside[:-1] if closing.get('contentName') else inside
                    chars.extend(self.captured(line, found, outer, closing.get('endCaptures', {})))
                elif 'match' in rule:
                    named = scopes + ((rule['name'],) if 'name' in rule else ())
                    chars.extend(self.captured(line, found, named, rule.get('captures', {})))
                else:
                    named = scopes + ((rule['name'],) if 'name' in rule else ())
                    chars.extend(self.captured(line, found, named, rule.get('beginCaptures', {})))
                    stack.append((rule, named + ((rule['contentName'],) if 'contentName' in rule else ())))
                if found.end() == found.start() and rule is not None and 'match' in rule:
                    if found.end() < len(line):
                        chars.append((line[found.end()], scopes))
                    pos = found.end() + 1
                else:
                    pos = found.end()
                if pos >= len(line) and found.end() == len(line):
                    break
            tokens = []
            for c, s in chars:
                if tokens and tokens[-1][1] == s:
                    tokens[-1][0] += c
                else:
                    tokens.append([c, s])
            lines.append([(t, s) for t, s in tokens])
        return lines, stack


@pytest.fixture(scope='module')
def grammar():
    return Grammar(json.loads(GRAMMAR.read_text()))


def scope_of(grammar, line, text):
    """The scopes of the first character of text's first occurrence in line."""
    (tokens,), _ = grammar.tokenize(line)
    at = line.index(text)
    for token, scopes in tokens:
        if at < len(token):
            return scopes
        at -= len(token)
    raise AssertionError((text, tokens))


@pytest.mark.parametrize(('line', 'text', 'scope'), [
    ('# a comment with "quotes" and {braces}', '# a comment with "quotes" and {braces}', 'comment.line.number-sign'),
    ('let x=1 # trailing', '# trailing', 'comment.line'),
    ('let x=1', 'let', 'storage.type'),
    ('const limit=10', 'const', 'storage.type'),
    ('if x >? 0 { return x } else { return 0 }', 'if', 'keyword.control'),
    ('if x >? 0 { return x } else { return 0 }', 'else', 'keyword.control'),
    ('if x >? 0 { return x } else { return 0 }', '>?', 'keyword.operator.comparison'),
    ('if x >? 0 { return x } else { return 0 }', 'return', 'keyword.control'),
    ('loop item in items { break $rows }', 'loop', 'keyword.control'),
    ('loop item in items { break $rows }', 'in', 'keyword.operator.word'),
    ('loop item in items { break $rows }', '$rows', 'entity.name.label'),
    ('let item=invoice(line) or_throw', 'or_throw', 'keyword.control'),
    ('if good is? error { }', 'is?', 'keyword.operator.comparison.word'),
    ('if a isnt? none and b notin? xs { }', 'isnt?', 'keyword.operator.comparison.word'),
    ('if a isnt? none and b notin? xs { }', 'notin?', 'keyword.operator.comparison.word'),
    ('if a isnt? none and b notin? xs { }', 'none', 'constant.language'),
    ('if a isnt? none and b notin? xs { }', 'and', 'keyword.operator.word'),
    ('let ok=a not=? b', 'not=?', 'keyword.operator.comparison'),
    ('let ok=xs .>=? 2', '.>=?', 'keyword.operator.comparison'),
    ('let t=true or false xor not ok', 'true', 'constant.language'),
    ('let t=true or false xor not ok', 'xor', 'keyword.operator.word'),
    ('let delay=300ms', '300', 'constant.numeric.decimal'),
    ('let delay=300ms', 'ms', 'keyword.other.unit'),
    ('let g=9.81m/s^2', 'm', 'keyword.other.unit'),
    ('let g=9.81m/s^2', '9.81', 'constant.numeric.decimal'),
    ('let big=1_000_000', '1_000_000', 'constant.numeric.decimal'),
    ('let e=2.5e-3', '2.5e-3', 'constant.numeric.decimal'),
    ('let mask=0xFF00', '0xFF00', 'constant.numeric.integer.based'),
    ('let bits=0b1010', '0b1010', 'constant.numeric.integer.based'),
    ('let data=0x"ff00"', '0x"ff00"', 'constant.numeric.bytes'),
    ('loop i in [0..n) { }', '0', 'constant.numeric.decimal'),
    ('loop i in [0..n) { }', '..', 'keyword.operator.range'),
    ('let all=[xs... 4]', '...', 'keyword.operator.spread'),
    ('let n=x ?? 0', '??', 'keyword.operator.coalesce'),
    ('let text="hi {name}!"', 'name', 'source.dewy.embedded'),
    ('let text="hi {name}!"', '{', 'punctuation.section.interpolation.begin'),
    ('let text="hi {name}!"', 'hi ', 'string.quoted.double'),
    ('let text="a\\tb\\u{1F642}"', '\\t', 'constant.character.escape'),
    ('let text="a\\tb\\u{1F642}"', '\\u{1F642}', 'constant.character.escape'),
    ("let text='single {x}'", 'single ', 'string.quoted.single'),
    ('let path=r"C:\\{raw}"', 'C:\\{raw}', 'string.quoted.raw.double'),
    ('from p"model.dewy" import fresh, advance', 'p', 'storage.type.string.prefix'),
    ('from p"model.dewy" import fresh, advance', 'model.dewy', 'string.quoted.double'),
    ('from p"model.dewy" import fresh, advance', 'from', 'keyword.control.import'),
    ('from p"model.dewy" import fresh, advance', 'import', 'keyword.control.import'),
    ('import p"model.dewy" as model', 'as', 'keyword.operator.word'),
    ('$runtime_assert (good.total =? 105)', '$runtime_assert', 'keyword.other.directive'),
    ('$assert(n >? 0, "positive")', '$assert', 'keyword.other.directive'),
    ('let next=($capture @count) => { count+=1 }', '$capture', 'keyword.other.directive'),
    ('let next=($capture @count) => { count+=1 }', '@', 'storage.modifier.reference'),
    ('let next=($capture @count) => { count+=1 }', '=>', 'storage.type.function.arrow'),
    ('let next=($capture @count) => { count+=1 }', '+=', 'keyword.operator.assignment.compound'),
    ('let ys=xs.map(@double)', '@', 'storage.modifier.reference'),
    ('let ys=xs.map(@double)', 'map', 'entity.name.function.member'),
    ('Point:type=[x:float64 y:float64]', 'Point', 'entity.name.type'),
    ('Point:type=[x:float64 y:float64]', 'type', 'support.type'),
    ('Point:type=[x:float64 y:float64]', 'float64', 'support.type.builtin'),
    ('Box:type=<T>[value:T]', 'Box', 'entity.name.type'),
    ('BadNumber:type=type of error & [text:string]', 'of', 'keyword.operator.word'),
    ('BadNumber:type=type of error & [text:string]', 'string', 'support.type.builtin'),
    ('advance=(@world:World dt:float64):>void=>{', 'advance', 'entity.name.function'),
    ('advance=(@world:World dt:float64):>void=>{', ':>', 'keyword.operator.type.returns'),
    ('advance=(@world:World dt:float64):>void=>{', 'World', 'entity.name.type'),
    ('advance=(@world:World dt:float64):>void=>{', 'void', 'support.type.builtin'),
    ('map_values=<T U>(values:array<T> f:<(x:T):>U>):>array<U>=> {', 'map_values', 'entity.name.function'),
    ('map_values=<T U>(values:array<T> f:<(x:T):>U>):>array<U>=> {', 'array', 'support.type.builtin'),
    ('double=(x:int64):>int64=>2*x', 'double', 'entity.name.function'),
    ('let scale=(f:float64)=>f*2.0', 'scale', 'entity.name.function'),
    ('world.velocity.x=(world.position.x-world.paddle)*4.0', 'x', 'variable.other.member'),
    ('let s=sum<int64 int64>(xs 0)', 'sum', 'entity.name.function.call'),
    ('printl("done")', 'printl', 'support.function.builtin'),
    ('let counts=["apple"->3 "pear"->5]', '->', 'keyword.operator.mapping'),
    ('let r=xs |> sorted', '|>', 'keyword.operator.pipe'),
    ('let value:(int64|string)?=none', '?', 'keyword.operator.type'),
    ('test "adds numbers" {', 'test', 'keyword.other.test'),
    ('let x=a//b', '//', 'keyword.operator.arithmetic'),
    ('let x=a.*b', '.*', 'keyword.operator.arithmetic'),
])
def test_grammar_scopes(grammar, line, text, scope):
    scopes = scope_of(grammar, line, text)
    assert any(s.startswith(scope) for s in scopes), (text, scopes)


@pytest.mark.parametrize(('line', 'text'), [
    ('let total=0', 'total'),          # plain names are left to semantic highlighting
    ('let testing=1', 'testing'),
    ('let test_value=1', 'test_value'),
    ('let x=value.length', 'length'),
])
def test_grammar_leaves_names_alone(grammar, line, text):
    scopes = scope_of(grammar, line, text)
    assert not any(s.startswith(('keyword', 'storage', 'constant')) for s in scopes), scopes


def test_grammar_multiline_strings(grammar):
    lines, stack = grammar.tokenize('let caption = """He said "go".\nNext frame: {42}"""\nlet after=1')
    assert any(s[-1].startswith('string.quoted.triple') for t, s in lines[0] if t == 'He said "go".')
    assert any('constant.numeric.decimal.dewy' in s for t, s in lines[1] if t == '42')
    assert any('storage.type.dewy' in s for t, s in lines[2] if t == 'let')
    assert stack == []


def test_grammar_covers_examples(grammar):
    """Every example and acceptance program ends where it began: no string or interpolation left open."""
    sources = sorted(ROOT.glob('examples/*.dewy')) + sorted(ROOT.glob('tests/ladder/*/design.dewy'))
    assert sources
    for source in sources:
        lines, stack = grammar.tokenize(source.read_text())
        assert stack == [], source
        assert sum(len(t) for line in lines for t, _ in line) + len(lines) - 1 == len(source.read_text()), source
