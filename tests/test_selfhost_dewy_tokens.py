"""compiler/dewy_tokens.dewy, the Dewy frontend's tokens (each one's spelling, the token a
spelling is, and the tokens related to one): it ships, and its frozen implementation-language
twin compiler/dewy_tokens.jo gives the same answers, also to Sloppy code that numbers the
tokens (`DewyToken(i)`). The oracle builds the spellings from their parts: punctuation, the
comparisons with `?`, `not` before a comparison, `.` before an elementwise operator, `=` after a
compound assignment's operator, the keywords as written, and the parser's labels for the
juxtapositions. A spelling is a token unless the lexer joins it itself (`not in?`, `and=`,
`or=`, `xor=`) or it is a label."""
import random
import re
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/selfhost'

PUNCTUATION = {'lparen': '(', 'rparen': ')', 'lbrack': '[', 'rbrack': ']', 'lbrace': '{', 'rbrace': '}',
               'langle': '<', 'rangle': '>', 'colon': ':', 'dot': '.', 'comma': ',', 'semi': ';', 'assign': '=',
               'plus': '+', 'minus': '-', 'star': '*', 'slash': '/', 'percent': '%', 'at': '@', 'amp': '&',
               'pipe': '|', 'caret': '^', 'question': '?', 'bang': '!', 'tilde': '~'}
OPERATORS = {'ellipsis': '...', 'function': '=>', 'returns': ':>', 'arrow': '->', 'coalesce': '??', 'floor': '//',
             'shl': '<<', 'shr': '>>', 'range': '..', 'pipe_right': '|>', 'pipe_left': '<|', 'angle_assign': '>=',
             'is_type': 'is?', 'isnt_type': 'isnt?', 'contains': 'in?', 'not_contains': 'not in?'}
COMPARISONS = {'eq': '=?', 'lt': '<?', 'gt': '>?', 'le': '<=?', 'ge': '>=?'}
KEYWORDS = ['let', 'const', 'return', 'break', 'continue', 'import', 'from', 'else', 'if', 'loop', 'match', 'test',
            'not', 'as', 'transmute', 'or', 'xor', 'and', 'in', 'of', 'or_throw', 'nand', 'nor', 'xnor', 'parallel',
            'concurrent', 'spawn']
LABELS = {'multiply_apply': 'MultiplyJuxtapose', 'call': 'CallJuxtapose', 'broadcast_call': 'CallJuxtaposeBroadcast',
          'index': 'IndexJuxtapose', 'type_apply': 'TypeParamJuxtapose', 'range_apply': 'RangeJuxtapose',
          'statement_end': 'SemicolonJuxtapose'}
JOINED = {'not_contains', 'and_assign', 'or_assign', 'xor_assign'}


def spellings():
    out = {'none': ''}
    out.update(PUNCTUATION)
    out.update(OPERATORS)
    out.update(COMPARISONS)
    out.update({f'not_{k}': 'not' + v for k, v in COMPARISONS.items()})
    out.update({f'kw_{w}': w for w in KEYWORDS})
    for k in ['plus', 'minus', 'star', 'slash', 'floor', 'percent', 'shl', 'shr', 'amp', 'pipe']:
        out[f'{k}_assign'] = out[k] + '='
    out['power_assign'] = '^='
    out.update({f'{w}_assign': w + '=' for w in ['and', 'or', 'xor']})
    for k in [*COMPARISONS, *(f'not_{k}' for k in COMPARISONS), 'plus', 'minus', 'star', 'slash', 'percent', 'floor']:
        out[f'dot_{k}'] = '.' + out[k]
    out['dot_caret'] = '.^'
    for k in ['plus', 'minus', 'star', 'slash', 'percent', 'floor', 'power']:
        out[f'dot_{k}_assign'] = '.' + out[f'{k}_assign']
    out.update(LABELS)
    return out


SPELLED = spellings()
BY_TEXT = {text: name for name, text in SPELLED.items() if name not in LABELS and name not in JOINED and text}


def kind(text):
    return BY_TEXT.get(text, 'none')


def syntax(text):
    if text == 'MultiplyJuxtapose':
        return 'multiply_apply'
    if text == 'CallJuxtaposeBroadcast':
        return 'broadcast_call'
    if text.startswith('CallJuxtapose'):
        return 'call'
    for name in ['index', 'type_apply', 'range_apply', 'statement_end']:
        if text == LABELS[name]:
            return name
    return kind(text)


def invert(t):
    return f'not_{t}' if t in COMPARISONS or t == 'contains' else 'none'


def uninvert(t):
    return t[4:] if t.startswith('not_') and invert(t[4:]) == t else t


def undot(t):
    return t[4:] if t.startswith('dot_') else 'none'


def assignment(t):
    return t.endswith('_assign') and t != 'angle_assign'


def order():
    """The tokens as dewy_tokens.dewy numbers them: its enumeration's members as written."""
    text = (ROOT / 'compiler/dewy_tokens.dewy').read_text()
    m = re.search(r"^DewyToken\s*:\s*type\s*=\s*('[^'\n]*'(?:\s*\|\s*'[^'\n]*')*)\s*$", text, re.M)
    return re.findall(r"'([^']*)'", m.group(1))


def low(b):
    return 'true' if b else 'false'


def expected(words):
    tokens = order()
    assert sorted(tokens) == sorted(SPELLED)
    lines = [f'{kind(w)} {syntax(w)}' for w in words]
    lines.append(' '.join(kind(chr(c)) if c < 128 and chr(c) in PUNCTUATION.values() else 'none' for c in range(256)))
    for t in tokens:
        lines.append(f'{t} [{SPELLED[t]}] {invert(t)} {undot(t)} {uninvert(t)} {low(assignment(t))} '
                     f'{low(t in ("statement_end", "assign") or assignment(t))} {low(t in ("call", "broadcast_call"))}')
    return lines


def words():
    out = sorted(set(SPELLED.values()) - {''}) + sorted(SPELLED) + ['', 'CallJuxtaposeX', 'CallJuxtapos', 'callJuxtapose',
                                                                   'AND', 'Let', 'not  in?', 'not in', 'in ?', '=?=',
                                                                   'é', 'é=', 'x', 'foo', '__', '0', '.', '..x']
    rng = random.Random(20261024)
    alphabet = sorted(set(''.join(SPELLED.values())))
    texts = [s for s in SPELLED.values() if s]
    for _ in range(400):
        if rng.random() < 0.5:
            out.append(''.join(rng.choice(alphabet) for _ in range(rng.randrange(1, 9))))
        else:
            s = rng.choice(texts)
            k = rng.randrange(len(s) + 1)
            out.append(rng.choice([s[:k], s[k:], s + rng.choice(alphabet), rng.choice(alphabet) + s]))
    return out


def build(compiler, source, binary, release):
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    return binary


def run(binary, args):
    ran = subprocess.run([binary, *args], capture_output=True, text=True, timeout=60)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    return ran.stdout.splitlines()


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_dewy_tokens_match_jo(compiler, tmp_path, release):
    args = words()
    want = expected(args)
    jo = run(build(compiler, FIXTURES / 'dewy_tokens_jo.jo', tmp_path / 'tokens-jo', release), args)
    assert jo == want
    # (Sloppy code over the Dewy module: the same tokens, numbered alike)
    over = tmp_path / 'dewy_tokens_over.jo'
    text = (FIXTURES / 'dewy_tokens_jo.jo').read_text()
    over.write_text(text.replace("use '../../../compiler/dewy_tokens.jo'",
                                 f"use '{(ROOT / 'compiler/dewy_tokens.dewy').as_posix()}'"))
    assert run(build(compiler, over, tmp_path / 'tokens-over', release), args) == want
    # (Dewy code lists the members in text order)
    dewy = run(build(compiler, FIXTURES / 'dewy_tokens_dewy.dewy', tmp_path / 'tokens-dewy', release), args)
    n = len(args) + 1
    assert dewy[:n] == want[:n]
    assert sorted(dewy[n:]) == sorted(want[n:])


@pytest.mark.core_quick
def test_selfhost_dewy_tokens_ships_dewy(compiler):
    binary = compiler.read_bytes()
    assert b'/compiler/dewy_tokens.dewy\0' in binary
    assert b'/compiler/dewy_tokens.jo\0' not in binary
