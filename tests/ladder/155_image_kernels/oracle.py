"""Independent image kernels over the same picture; run with --write to refresh expected.out
(and --picture to regenerate scene.pgm)."""
from fractions import Fraction
from pathlib import Path
import json
import sys

HERE = Path(__file__).parent
SHADES = " .:-=+*#%@"


def command_line():
    return json.loads((HERE.parent / 'ladder.json').read_text())['programs'][HERE.name]['args']


def picture():
    """A 36x20 scene, values up to 1000: a gradient sky, a disc, a bar, two specks, noise."""
    w, h, top = 36, 20, 1000
    seed = 12345
    rows = []
    for y in range(h):
        row = []
        for x in range(w):
            v = 80 + 6 * y
            if (x - 9) ** 2 + (y - 8) ** 2 <= 30:
                v = 900
            if 20 <= x <= 31 and 12 <= y <= 15:
                v = 760
            if (x, y) in ((33, 2), (34, 2), (2, 17)):
                v = 990
            seed = (seed * 1103515245 + 12345) % 2 ** 31
            v = max(0, min(top, v + seed % 41 - 20))
            row.append(v)
        rows.append(row)
    lines = ['P2', '# a disc, a bar and specks over a gradient', f'{w} {h}', str(top)]
    for row in rows:
        lines.append(' '.join(str(v) for v in row))
    return '\n'.join(lines) + '\n'


def parse(text):
    words = []
    for line in text.splitlines():
        words.extend(line.split('#')[0].split())
    assert words[0] == 'P2'
    w, h, top = int(words[1]), int(words[2]), int(words[3])
    vals = [int(x) for x in words[4:]]
    assert len(vals) == w * h
    return w, h, [(v * 255 + top // 2) // top for v in vals]


def at(img, x, y):
    w, h, px = img
    return px[max(0, min(h - 1, y)) * w + max(0, min(w - 1, x))]


def blur(img, r):
    w, h, px = img
    area = (2 * r + 1) ** 2
    out = []
    for i in range(len(px)):
        x, y = i % w, i // w
        total = sum(at(img, x + dx, y + dy) for dy in range(-r, r + 1) for dx in range(-r, r + 1))
        out.append(min(255, (total + area // 2) // area))
    return w, h, out


def edges(img):
    w, h, px = img
    out = []
    for i in range(len(px)):
        x, y = i % w, i // w
        p = lambda dx, dy: at(img, x + dx, y + dy)
        gx = p(1, -1) + 2 * p(1, 0) + p(1, 1) - p(-1, -1) - 2 * p(-1, 0) - p(-1, 1)
        gy = p(-1, 1) + 2 * p(0, 1) + p(1, 1) - p(-1, -1) - 2 * p(0, -1) - p(1, -1)
        out.append(min(255, abs(gx) + abs(gy)))
    return w, h, out


def otsu(counts):
    n = sum(counts)
    s = sum(v * c for v, c in enumerate(counts))
    n0 = s0 = 0
    best, pick = Fraction(-1), 0
    for t in range(256):
        n0 += counts[t]
        s0 += t * counts[t]
        n1 = n - n0
        if n0 == 0 or n1 == 0:
            continue
        spread = Fraction((n * s0 - s * n0) ** 2, n0 * n1)
        if spread > best:
            best, pick = spread, t
    return pick


def stretch(img):
    w, h, px = img
    lo, hi = min(px), max(px)
    if hi == lo:
        return img
    return w, h, [max(0, min(255, ((v - lo) * 255 + (hi - lo) // 2) // (hi - lo))) for v in px]


def regions(img, mask):
    w, h, px = img
    n = len(px)
    seen = [False] * n
    found = []
    for start in range(n):
        if seen[start] or not mask[start]:
            continue
        seen[start] = True
        todo = [start]
        size, left, topy, right, bottom = 0, start % w, start // w, start % w, start // w
        while todo:
            i = todo.pop()
            x, y = i % w, i // w
            size += 1
            left, topy, right, bottom = min(left, x), min(topy, y), max(right, x), max(bottom, y)
            near = []
            if x > 0:
                near.append(i - 1)
            if x < w - 1:
                near.append(i + 1)
            if i >= w:
                near.append(i - w)
            if i + w < n:
                near.append(i + w)
            for j in near:
                if not seen[j] and mask[j]:
                    seen[j] = True
                    todo.append(j)
        found.append((size, left, topy, right, bottom))
    found.sort(key=lambda r: (-r[0], r[2], r[1]))
    return found


def show(img, title, out):
    w, h, _ = img
    out.append(f'{title}:')
    for y in range(h):
        out.append('  |' + ''.join(SHADES[at(img, x, y) * 10 // 256] for x in range(w)) + '|')


def half_up(f, places):
    """Format a nonnegative Fraction to `places` decimals, halves rounded away from zero."""
    scaled = f * 10 ** places
    q = int(scaled)
    if scaled - q >= Fraction(1, 2):
        q += 1
    s = str(q).rjust(places + 1, '0')
    return f'{s[:-places]}.{s[-places:]}'


def run(args):
    path = Path(args[0].replace('{dir}', str(HERE)))
    radius, invert = 1, False
    for a in args[1:]:
        if a.startswith('radius='):
            radius = int(a.split('=')[1])
        elif a == '--invert':
            invert = True
    img = parse(path.read_text())
    w, h, px = img
    out = [f'{path.name}: {w}x{h}, mean level {half_up(Fraction(sum(px), len(px)), 2)}']
    soft = blur(img, radius)
    strong = edges(soft)
    show(stretch(soft), f'blurred, radius {radius}, stretched', out)
    show(strong, 'edges', out)
    counts = [0] * 256
    for v in soft[2]:
        counts[v] += 1
    busiest = sorted(range(256), key=lambda v: -counts[v])
    out.append('most common levels: ' + ', '.join(f'{v} ({counts[v]})' for v in busiest[:3]))
    t = otsu(counts)
    mask = [(v <= t) if invert else (v > t) for v in soft[2]]
    side = 'dark' if invert else 'light'
    out.append(f'otsu threshold {t}: {sum(mask)} {side} pixels')
    found = regions(soft, mask)
    out.append(f'{len(found)} {side} regions')
    for size, left, topy, right, bottom in found[:5]:
        out.append(f'  {size:>4} pixels, x {left}..{right}, y {topy}..{bottom}')
    strongest = max(strong[2])
    rim = sum(1 for v in strong[2] if v * 2 >= strongest)
    out.append(f'strongest edge {strongest}; {rim} pixels at half of it or more')
    return '\n'.join(out) + '\n'


def main():
    if '--picture' in sys.argv:
        (HERE / 'scene.pgm').write_text(picture())
    got = run(command_line())
    if '--write' in sys.argv:
        (HERE / 'expected.out').write_text(got)
    elif (HERE / 'expected.out').read_text() != got:
        sys.exit('expected.out differs from the oracle')


if __name__ == '__main__':
    main()
