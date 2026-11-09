#!/usr/bin/env python3
"""Generate lib/time/rules/current.bin, the zone rules a Dewy version ships, from compiled TZif files.

Usage: tools/time/gen_rules.py [ZONEINFO_DIR] [OUTPUT] [WINDOWS_ZONES_XML]

Pack layout, little-endian:
  'DZP2', u32 zone count, u32 data version offset, u32 data version length,
  u32 Windows name count, u32 Windows table offset,
  then for each zone name in byte order: u32 name offset, u32 name length, u32 record offset.
  The Windows table (CLDR windowsZones, territory 001), by name in byte order: u32 name offset,
  u32 name length, u32 zone index.
  A record: i32 offset before the first change, u32 change count, u32 rule offset, u32 rule length,
  then i64 change times (POSIX seconds), then i32 offsets, then u8 daylight flags.
Names, rules and the version live in a string area after the records. Links share a record,
and each keeps its own name.
"""
import pathlib
import re
import struct
import sys


def read_tzif(path):
    data = path.read_bytes()
    if data[:4] != b'TZif':
        return None
    version = data[4]
    def header(at):
        return struct.unpack('>6L', data[at + 20:at + 44])
    isut, isstd, leap, timecnt, typecnt, charcnt = header(0)
    at = 44 + timecnt * 5 + typecnt * 6 + charcnt + leap * 8 + isstd + isut
    assert version >= ord('2'), path
    isut, isstd, leap, timecnt, typecnt, charcnt = header(at)
    at += 44
    times = struct.unpack(f'>{timecnt}q', data[at:at + timecnt * 8]); at += timecnt * 8
    indexes = data[at:at + timecnt]; at += timecnt
    types = [struct.unpack('>lBB', data[at + i * 6:at + i * 6 + 6]) for i in range(typecnt)]
    at += typecnt * 6 + charcnt + leap * 12 + isstd + isut
    footer = data[at:].strip(b'\n').decode()
    first = next((t for t in types if not t[1]), types[0])[0]
    if types:
        first = types[0][0]
    # Drop the "big bang" sentinel and changes that change nothing.
    changes = []
    last = first
    for moment, index in zip(times, indexes):
        offset, dst, _ = types[index]
        if moment <= -2**59:
            first = last = offset
            continue
        if offset == last and changes and changes[-1][2] == dst:
            continue
        changes.append((moment, offset, dst))
        last = offset
    return first, changes, footer


def names_of(root):
    # tzdata.zi lists every zone and link, which excludes posix/, right/ and the tables.
    names = set()
    for line in (root / 'tzdata.zi').read_text().splitlines():
        words = line.split()
        if not words:
            continue
        if words[0] == 'Z':
            names.add(words[1])
        elif words[0] == 'L':
            names.add(words[2])
    return sorted(names, key=str.encode)


def version_of(root):
    first = (root / 'tzdata.zi').read_text().splitlines()[0]
    return 'iana-' + first.split()[-1]


# CLDR keeps the tz names it first used; a renamed zone answers to its current name, as a
# Linux machine set to the same place does (`India Standard Time` is Asia/Kolkata, not Asia/Calcutta).
CLDR_RENAMED = {
    'America/Buenos_Aires': 'America/Argentina/Buenos_Aires', 'America/Catamarca': 'America/Argentina/Catamarca',
    'America/Cordoba': 'America/Argentina/Cordoba', 'America/Jujuy': 'America/Argentina/Jujuy',
    'America/Mendoza': 'America/Argentina/Mendoza', 'America/Godthab': 'America/Nuuk',
    'America/Indianapolis': 'America/Indiana/Indianapolis', 'America/Louisville': 'America/Kentucky/Louisville',
    'Asia/Calcutta': 'Asia/Kolkata', 'Asia/Katmandu': 'Asia/Kathmandu', 'Asia/Rangoon': 'Asia/Yangon',
    'Asia/Saigon': 'Asia/Ho_Chi_Minh', 'Atlantic/Faeroe': 'Atlantic/Faroe', 'Europe/Kiev': 'Europe/Kyiv',
    'Pacific/Enderbury': 'Pacific/Kanton', 'Pacific/Ponape': 'Pacific/Pohnpei', 'Pacific/Truk': 'Pacific/Chuuk',
}


def windows_names(path, names):
    pairs = re.findall(r'<mapZone other="([^"]+)" territory="001" type="([^" ]+)', path.read_text())
    pairs = [(w, CLDR_RENAMED.get(z, z)) for w, z in pairs]
    return sorted(((w.encode(), z) for w, z in pairs if z in names), key=lambda pair: pair[0])


def main():
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else '/usr/share/zoneinfo')
    output = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else
                          pathlib.Path(__file__).resolve().parents[2] / 'lib/time/rules/current.bin')
    names = names_of(root)
    xml = pathlib.Path(sys.argv[3] if len(sys.argv) > 3 else '/usr/share/evolution-data-server/ews/windowsZones.xml')
    windows = windows_names(xml, set(names))
    records = {}
    zones = []
    strings = bytearray()
    interned = {}

    def text(value):
        raw = value.encode()
        if raw not in interned:
            interned[raw] = len(strings)
            strings.extend(raw)
        return interned[raw], len(raw)

    body = bytearray()
    index_size = 12 * len(names)
    start = 24 + index_size
    for name in names:
        parsed = read_tzif(root / name)
        key = repr(parsed)
        if key not in records:
            first, changes, footer = parsed
            rule_at, rule_len = text(footer)
            records[key] = start + len(body)
            body += struct.pack('<lLLL', first, len(changes), rule_at, rule_len)
            body += b''.join(struct.pack('<q', c[0]) for c in changes)
            body += b''.join(struct.pack('<l', c[1]) for c in changes)
            body += bytes(c[2] for c in changes)
        zones.append((text(name), records[key]))
    version_at, version_len = text(version_of(root))
    windows_rows = []
    for raw, zone in windows:
        name_at, name_len = text(raw.decode())
        windows_rows.append((name_at, name_len, names.index(zone)))
    windows_at = start + len(body)
    body += b'\0' * (12 * len(windows_rows))
    strings_at = start + len(body)
    for i, (name_at, name_len, zone) in enumerate(windows_rows):
        struct.pack_into('<LLL', body, windows_at - start + 12 * i, strings_at + name_at, name_len, zone)
    out = bytearray(b'DZP2')
    out += struct.pack('<LLLLL', len(zones), strings_at + version_at, version_len, len(windows_rows), windows_at)
    for (name_at, name_len), record in zones:
        out += struct.pack('<LLL', strings_at + name_at, name_len, record)
    out += body + strings
    # Rule offsets are stored relative to the string area: make them absolute.
    for key, record in records.items():
        at = record + 8
        rule_at = struct.unpack_from('<L', out, at)[0]
        struct.pack_into('<L', out, at, strings_at + rule_at)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(out)
    print(f'{output}: {len(out)} bytes, {len(zones)} names, {len(records)} records, {len(windows_rows)} Windows names, {version_of(root)}')


if __name__ == '__main__':
    main()
