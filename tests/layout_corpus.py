"""Build deterministic layout variants once per distinct source corpus."""
import random
from functools import lru_cache


@lru_cache(maxsize=1)
def layout_texts(sources, random_state, lex, disturbed, error):
    rng = random.Random()
    rng.setstate(random_state)
    texts = []
    for src in sources:
        try:
            src.decode()
            lex(src)
        except (UnicodeDecodeError, error):
            continue
        texts.append(src)
        for _ in range(2):
            if (text := disturbed(src, rng)) is not None:
                texts.append(text)
    texts += [b'', b'\n', b'f(\n', b')\n', b'x = [1\n  2}\n', b'#{ a\n b }# x=1\n  y=2\n', b'a = {\r\nb\r\n}',
              b'let s="a\n   b" c=(\n1\n)\n', b'x:array<array<int64>>=[]\n', b'  # alone  \n\t\n',
              b'm = [w = () => 1 v=2]\n', b'f(a=1 b = 2)\n', b'x = a\nand b\n', b'y=a +\nb\n',
              b'(' * 300 + b')' * 300 + b'\n', b'p = <T>(x:T) => x\n', b'q:>int64=x>=?1\n']
    return tuple(texts)
