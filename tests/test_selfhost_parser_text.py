"""Source text, string tokens and parse units agree with the frozen Jo parser."""
import subprocess

from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401


DRIVER = r'''use 'main.jo'
use 'parse.jo'
use 'parser_text.dewy'
use 'lex.jo'
use 'lexer_helpers.dewy'
use 'ast.jo'
use 'node_store.dewy'
use 'source_types.dewy'
use 'util.jo'
show = (s: str) -> str:
    out = ""
    loop c in s: out = out + "{int(c)},"
    out
dump = (label: str, decls: int[]):
    print("case:{label}:decls:{decls}:nodes:{nodes.len()}:lists:{lists}")
    loop i in [1..nodes.len()):
        n = nodes[i]
        text = ""
        if n.kind == .str_lit or n.kind == .pair:
            if n.sval > 0: text = show(name_of(int(n.sval)))
        print("node:{i}:{int(n.kind)}:{n.op}:{n.a}:{n.b}:{n.c}:{n.name}:{n.sval}:{n.ival}:{n.flags}:{n.aux}:{n.aux2}:{n.list}:{n.nlist}:{text}")
main = ():
    init_keywords()
    loop text in [
{CASES}
    ]:
        files = [SrcFile(path="text.jo", src=text)]
        nodes = [Node()]; lists = []
        dump(show(text), parse_file(0))
    # a library unit, spans and lazy bodies
    src = {LAZY}
    files = [SrcFile(path="lazy.jo", src=src)]
    nodes = [Node()]; lists = []
    p_lazy = true
    decls = parse_file(0)
    p_lazy = false
    loop d in decls:
        if nodes[d].kind == .fn_: ensure_body(d)
    dump("lazy", decls)
    nodes = [Node()]; lists = []
    dump("span", parse_span(0, 0, 38))
    loop s in [{DEDENT}]:
        print("dedent:{show(s)}:{show(dedent_triple(s))}")
    loop s in [{DECODE}]:
        print("decode:{show(s)}:{show(decode_str(s, 0, false))}:{show(decode_str(s, 0, true))}")
    loop s in [{IDENT}]:
        print("ident:{show(s)}:{is_ident_plain(s)}")
'''


def jo_text(s):
    """s as a Jo string literal (braces doubled, other bytes escaped)."""
    out = []
    for b in s.encode() if isinstance(s, str) else s:
        c = chr(b)
        if c == '\\': out.append('\\\\')
        elif c == '"': out.append('\\"')
        elif c == '\n': out.append('\\n')
        elif c == '\r': out.append('\\r')
        elif c == '\t': out.append('\\t')
        elif c == '{': out.append('{{')
        elif c == '}': out.append('}}')
        elif 32 <= b < 127: out.append(c)
        else: out.append('\\x%02x' % b)
    return '"' + ''.join(out) + '"'


# Jo sources whose strings cover escapes, braces, interpolation boundaries and formats,
# raw and triple-quoted text (tabs, CRLF, blank lines), empty strings and UTF-8 or invalid bytes.
CASES = [
    'a = ""\nb = \'\'\nc = \'x\'\nd = \'\u00e9\'\ne = \'\u20ac\'\nf = \'\U0001f642\'\n',
    'a = "\\n\\t\\r\\0\\\\\\"\\\'\\{\\}\\e\\x41\\x7f"\nb = "one \\\n     two"\n',
    'a = "{{x}} and {{{{ }}}}"\nb = "}}{{"\nc = "{"\nd = "\\{"\n',
    'a = "v={x} w={y:>8.2f} z={n:,}"\nb = "{x=}"\nc = "{x = }"\n',
    'a = "{f("in}")} {xs[0]:5} {m["k"]}"\nb = "{if c: "yes" else: "no"}"\n',
    'a = "pre {  x  } post"\nb = "{a}{b}{c}"\nc = "{x}\\n"\n',
    'a = r"\\d+{x}"\nb = r\'\\w\'\n',
    'a = """\n    one\n      two\n    three\n    """\n',
    'a = """\r\n\tone\r\n\t\ttwo\r\n\t"""\n',
    'a = """\n  x {v}\n\n    y\n  """\nb = """{{}}"""\nc = """"""\n',
    'a = "caf\u00e9 {n} \u20ac"\nb = "\\xff\\xfe raw"\n',
]
LAZY = 'f = (x: int) -> int:\n    return "{x}"\n\ng = ():\n    pass\nh = 1\n'
DEDENT = ['', '\n', '\r\n  a\r\n  b\r\n', '\n\t\tx\n\t y\n\t', '\n   \n  z\n', '  lone']
DECODE = ['', 'a{{b}}c', '\\\\\\n', 'x\\\n   y', '\u00e9\\x00']
IDENT = ['', '_a1', '1a', 'a-b', '\u00e9']
DRIVER = (DRIVER.replace('{CASES}', ',\n'.join('        ' + jo_text(c) for c in CASES))
          .replace('{LAZY}', jo_text(LAZY))
          .replace('{DEDENT}', ', '.join(map(jo_text, DEDENT)))
          .replace('{DECODE}', ', '.join(map(jo_text, DECODE)))
          .replace('{IDENT}', ', '.join(map(jo_text, IDENT))))


def test_parser_text_match_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('parser_text',))
    outputs = [subprocess.run([binary], capture_output=True, timeout=60)
               for binary in binaries]
    assert all(result.returncode == 0 for result in outputs), [
        (result.returncode, result.stderr) for result in outputs]
    assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
    assert outputs[0].stdout.count(b'case:') == 13
    assert outputs[0].stdout.count(b'dedent:') == 6
