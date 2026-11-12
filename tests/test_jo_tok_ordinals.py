"""Numeric Tok ordinals written into Dewy compiler leaves match the frozen Jo enum."""
import re
import subprocess

from tests.support import ROOT, compiler  # noqa: F401


def frozen_tok():
    text = (ROOT / 'compiler/checker_tokens.jo').read_text()
    body = re.sub(r'#.*', '', text.split('enum Tok:')[1].split('\n\n')[0])
    names = [name.strip() for name in body.replace('\n', ',').split(',') if name.strip()]
    return {name: i for i, name in enumerate(names)}


def written_ordinals():
    """(file, line, name, number) for each ordinal a leaf names as a frozen Tok one: `=58 # Frozen Tok.plus
    ordinal.`, a comment naming one above the line that uses it, or a comment listing `name N` pairs."""
    tok = frozen_tok()
    found = []
    for path in sorted((ROOT / 'compiler').glob('*.dewy')):
        lines = path.read_text().splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            here = re.search(r'(\d+)\s*\}?\s*# Frozen Tok\.(\w+) ordinal', line)
            if here:
                found.append((path.name, i + 1, here[2], int(here[1])))
            elif re.search(r'[Ff]rozen Tok', line) and '#' in line:
                comment = [line[line.index('#'):]]
                j = i + 1
                while j < len(lines) and lines[j].lstrip().startswith('#'):
                    comment.append(lines[j])
                    j += 1
                pairs = [(name, int(n)) for name, n in re.findall(r'(?:Tok\.)?\b([a-z_]+) (\d+)', ' '.join(comment))
                         if name in tok]
                single = re.search(r'Frozen Tok\.(\w+) ordinal', line)
                if single and not pairs and j < len(lines):
                    used = re.findall(r'\b(\d+)\b', lines[j])
                    assert str(tok[single[1]]) in used, (path.name, j + 1, single[1], used)
                    pairs = [(single[1], tok[single[1]])]
                found += [(path.name, i + 1, name, n) for name, n in pairs]
                i = j
                continue
            i += 1
    return found


def test_written_tok_ordinals_match_the_frozen_enum():
    tok = frozen_tok()
    found = written_ordinals()
    names = {name for _, _, name, _ in found}
    # (the parser leaves' writes: an open range start, assignments and compound updates)
    assert {'plus', 'assign', 'dotop', 'ampeq', 'pipeeq', 'careteq'} <= names, names
    wrong = [(f, line, name, n, tok[name]) for f, line, name, n in found if tok[name] != n]
    assert not wrong, wrong


def test_jo_parser_operator_ordinals(compiler, tmp_path):
    # Field defaults and `^=`, `.+=` (Tok.assign, Tok.dotop) and `and=`, `or=`, `xor=` (Tok.ampeq, pipeeq,
    # careteq): the Dewy parser leaves write each as a frozen ordinal.
    (tmp_path / 'ops.jo').write_text('struct P:\n    x: int\n    y = 2\n\n'
                                     'total = () -> int:\n'
                                     '    p = P(x = 1)\n'
                                     '    a = 6\n    a and= 3\n'
                                     '    b = 4\n    b or= 1\n'
                                     '    c = 6\n    c xor= 3\n'
                                     '    d = 2\n    d ^= 3\n'
                                     '    xs = [1, 2]\n    xs .+= [10, 20]\n'
                                     '    return p.y * 10000000 + a * 1000000 + b * 100000 + c * 10000 + d * 1000 + xs[0] + xs[1]\n')
    # Combined and many-name loops unpack each element with a synthesized `=` (Tok.assign).
    (tmp_path / 'unpack.jo').write_text('unpacked = () -> int:\n'
                                        '    pairs = [(1, 2), (3, 4)]\n'
                                        '    s = 0\n'
                                        '    loop i in 0.. and p, q in pairs:\n'
                                        '        s = s * 10 + p + q + i\n'
                                        '    ts = [(1, 2, 3)]\n'
                                        '    loop a, b, c in ts:\n'
                                        '        s = s * 10 + a + b + c\n'
                                        '    return s\n')
    path = tmp_path / 'user.dewy'
    path.write_text('from p"ops.jo" import total\nfrom p"unpack.jo" import unpacked\n'
                    'main=()=>{\n    printl(total())\n    printl(unpacked())\n}\n')
    binary = tmp_path / 'user'
    built = subprocess.run([compiler, 'build', path, '-o', binary], text=True, capture_output=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], text=True, capture_output=True, timeout=30)
    assert ran.stdout == '22558033\n386\n', ran.stdout + ran.stderr
