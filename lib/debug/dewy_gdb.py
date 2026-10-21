# gdb printers for Dewy programs built with `dewy build -g`: every value shows as
# Dewy prints it inside a container (`"{[value]}"`): a string quoted, an array
# or record as its literal, an optional or union as its value, an `int` as its
# number (word or BigInt). Load them with
#     gdb -x <dewy>/lib/debug/dewy_gdb.py ./program
# (or `source` this file in gdb, or in ~/.gdbinit).
#
# A string or an array is a pointer to [rc][len][cap][data...] (null: empty); an
# optional `T?` is its value followed by a flag; a field whose type holds the
# record it is in (next: Node?) is a pointer to [rc][value] (null: none). An
# `int` is a word: even, the value shifted left one bit; odd, one more than the
# address of a one-element BigInt array header ([sign:int64 limbs:array<uint64>],
# each limb 32 bits of the magnitude, least significant first).
import gdb

LIMIT = 200         # elements shown of a long array
TEXT_LIMIT = 10000  # bytes shown of a long string
DATA = 24           # where the elements start, after rc, len and cap
MASK = (1 << 64) - 1


def _limit(default):
    """gdb's `print elements` (0 or None: no limit), else the default"""
    try:
        n = gdb.parameter("print elements")
    except gdb.error:
        return default
    if n is None or n == 0:
        return 1 << 30
    return min(int(n), default)


def _memory(address, size):
    return gdb.selected_inferior().read_memory(address, size).tobytes()


def _word(address):
    return int.from_bytes(_memory(address, 8), "little", signed=True)


def _length(pointer):
    return 0 if pointer == 0 else _word(pointer + 8)


def _name(t):
    return t.name or t.strip_typedefs().name or ""


def _text(pointer):
    n = _length(pointer)
    if n <= 0:
        return '""'
    raw = _memory(pointer + DATA, min(n, TEXT_LIMIT))
    text = raw.decode("utf-8", "replace").replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return '"' + text + ('..."' if n > TEXT_LIMIT else '"')


def tagged_int(word):
    """the value of an `int` word"""
    word &= MASK
    if word & 1 == 0:
        return (word ^ (1 << 63)) - (1 << 63) >> 1
    big = ((word - 1) & MASK) + DATA
    sign = _word(big)
    limbs = _word(big + 8) & MASK
    value = 0
    for i in range(_length(limbs)):
        value += (_word(limbs + DATA + 8 * i) & MASK) << (32 * i)
    return -value if sign < 0 else value


def _array(val, elem):
    pointer = int(val) & MASK
    n = _length(pointer)
    if n == 0 or elem is None:
        return "[]"
    shown = min(n, _limit(LIMIT))
    first = gdb.Value(pointer + DATA).cast(elem.pointer())
    items = [show((first + i).dereference()) for i in range(shown)]
    return "[" + " ".join(items) + (" …" if n > shown else "") + "]"


def _elements(val):
    """an array value's elements (from its header's flexible data member)"""
    header = val.type.strip_typedefs().target().strip_typedefs()
    data = [f for f in header.fields() if f.name == "data"]
    return data[0].type.strip_typedefs().target() if data else None


def show(val):
    """a value as Dewy text"""
    t = val.type.strip_typedefs()
    name = _name(val.type)
    if name == "int" and t.code == gdb.TYPE_CODE_INT:
        return str(tagged_int(int(val)))
    if name == "string":
        return _text(int(val) & MASK)
    if t.code == gdb.TYPE_CODE_PTR:
        target = t.target().strip_typedefs()
        if (target.name or "").endswith(" box"):
            pointer = int(val) & MASK
            if pointer == 0:
                return "none"
            return show(val.dereference()["value"])
        if (target.name or "").endswith("[] header") or name.startswith("array<"):
            return _array(val, _elements(val))
        return str(val)
    if t.code == gdb.TYPE_CODE_BOOL:
        return "true" if bool(val) else "false"
    if t.code == gdb.TYPE_CODE_INT or t.code == gdb.TYPE_CODE_FLT:
        return str(val)
    if t.code == gdb.TYPE_CODE_ENUM:
        return str(val)
    if t.code == gdb.TYPE_CODE_ARRAY:
        low, high = t.range()
        return "[" + " ".join(show(val[i]) for i in range(low, high + 1)) + "]"
    if t.code != gdb.TYPE_CODE_STRUCT:
        return str(val)
    fields = [f.name for f in t.fields()]
    if fields == ["value", "has"] and name.endswith("?"):
        return show(val["value"]) if bool(val["has"]) else "none"
    if fields == ["__keys", "vals", "slots", "hashes", "gone", "ngone"]:
        return _dict(val)
    if fields[:1] == ["tag"] and t.fields()[0].type.strip_typedefs().code == gdb.TYPE_CODE_ENUM:
        tag = str(val["tag"])
        if tag not in fields:
            return tag
        member = val[tag]
        inner = [f.name for f in member.type.strip_typedefs().fields()]
        if inner == ["0"]:
            return show(member["0"])
        return tag + _record(member)
    return _record(val)


def _record(val):
    t = val.type.strip_typedefs()
    return "[" + " ".join("%s=%s" % (f.name, show(val[f.name])) for f in t.fields() if f.name) + "]"


def _dict(val):
    keys = int(val["__keys"]) & MASK
    values = int(val["vals"]) & MASK
    gone = int(val["gone"]) & MASK
    n = _length(keys)
    key_type, value_type = _elements(val["__keys"]), _elements(val["vals"])
    entries = []
    for i in range(min(n, _limit(LIMIT))):
        if gone and i < _length(gone) and _memory(gone + DATA + i, 1) != b"\0":
            continue
        k = gdb.Value(keys + DATA).cast(key_type.pointer()) + i
        v = gdb.Value(values + DATA).cast(value_type.pointer()) + i
        entries.append("%s -> %s" % (show(k.dereference()), show(v.dereference())))
    return "[" + " ".join(entries) + "]" if entries else "[->]"


class DewyPrinter:
    def __init__(self, val):
        self.val = val

    def to_string(self):
        try:
            return show(self.val)
        except gdb.error as error:
            return "<unreadable: %s>" % error


def lookup(val):
    t = val.type.strip_typedefs()
    name = _name(val.type)
    if name == "int" and t.code == gdb.TYPE_CODE_INT:
        return DewyPrinter(val)
    if name == "string" or name.startswith("array<"):
        return DewyPrinter(val)
    if t.code == gdb.TYPE_CODE_PTR and (t.target().strip_typedefs().name or "").endswith(" box"):
        return DewyPrinter(val)
    if t.code == gdb.TYPE_CODE_STRUCT and not name.endswith(" box") and not name.endswith(" header"):
        return DewyPrinter(val)
    return None


gdb.pretty_printers.append(lookup)
