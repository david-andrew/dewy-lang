"""Independent image arithmetic and native layout; --write refreshes expected.out."""
import ctypes
from pathlib import Path
import sys


def expected():
    source = [(1000, 2000, 3000, 0), (12000, 40000, 8000, 65535),
              (65535, 1000, 2000, 32000), (0, 32000, 64000, 1000),
              (40000, 50000, 60000, 64000), (500, 1000, 1500, 50000)]
    exposed = [tuple(min(65535, c * 2) for c in p[:3]) + p[3:] for p in source]
    def stats(pixels):
        return [len(pixels)] + [sum(p[channel] for p in pixels) for channel in range(3)]
    def show(label, values):
        return f'{label}: pixels={values[0]} red={values[1]} green={values[2]} blue={values[3]}'
    before, after = stats(source), stats(exposed)
    lines = [show('original', before), show('exposed', after),
             show('combined', [a+b for a, b in zip(before, after)])]
    class Pixel(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint16) for name in ('r', 'g', 'b', 'alpha')]
    size, alignment = ctypes.sizeof(Pixel), ctypes.alignment(Pixel)
    rgb = [c >> 8 for pixel in exposed for c in pixel[:3]]
    lines += [f'buffer: capacity={len(source)*size} written={len(rgb)} stride={size} alignment={alignment}',
              f'rgb: bytes={len(rgb)} weighted checksum={sum(i*c for i, c in enumerate(rgb, 1))}',
              'preview: ' + ' '.join(f'{c:02x}' for c in rgb)]
    hit = next(p for p in exposed if p[3] == 32000)
    assert not any(p[3] == 12345 for p in exposed)
    lines += ['alpha hit: ' + ' '.join(map(str, hit)),
              'lookup: hit=1 miss=0 null=true', 'nullable pointer layout: true',
              'source unchanged: true', show('black', [len(source), 0, 0, 0])]
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    path = Path(__file__).with_name('expected.out')
    if '--write' in sys.argv:
        path.write_text(expected())
    else:
        assert path.read_text() == expected()
        print('135 oracle: matched')
