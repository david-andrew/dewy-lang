# gdb printers for Sloppy programs built with `sloppy build -g`: strings as text, arrays as their
# elements, optionals as their value or none. Load them with
#     gdb -x <sloppy>/lib/debug/sloppy_gdb.py ./game
# (or `source` this file in gdb, or in ~/.gdbinit).
#
# A string or an array is a pointer to [rc][len][cap][data...] (null: empty); an optional `T?` is
# its value followed by a flag.
import gdb

LIMIT = 200         # elements shown of a long array
TEXT_LIMIT = 10000  # bytes shown of a long string


def _limit(default):
    """gdb's `print elements` (0 or None: no limit), else the default"""
    try:
        n = gdb.parameter("print elements")
    except gdb.error:
        return default
    if n is None or n == 0:
        return 1 << 30
    return int(n)


def _header(val):
    """the header a string or array value points to, or None (empty)"""
    p = val.cast(val.type.strip_typedefs())
    if int(p) == 0:
        return None
    return p.dereference()


class StrPrinter:
    def __init__(self, val):
        self.val = val

    def to_string(self):
        h = _header(self.val)
        if h is None:
            return '""'
        n = int(h["len"])
        if n <= 0:
            return '""'
        limit = min(_limit(TEXT_LIMIT), TEXT_LIMIT)
        data = int(h["data"].address)
        raw = gdb.selected_inferior().read_memory(data, min(n, limit)).tobytes()
        text = raw.decode("utf-8", "replace").replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return '"' + text + ('..."' if n > limit else '"')


class ArrayPrinter:
    def __init__(self, val):
        self.val = val
        self.h = _header(val)

    def _len(self):
        return 0 if self.h is None else int(self.h["len"])

    def to_string(self):
        return "{}" if self._len() == 0 else None

    def children(self):
        if self.h is None:
            return
        elem = self.h["data"].type.strip_typedefs().target()
        first = self.h["data"].address.cast(elem.pointer())
        for i in range(min(self._len(), _limit(LIMIT))):
            yield "[%d]" % i, (first + i).dereference()

    def display_hint(self):
        return "array"


class OptPrinter:
    def __init__(self, val):
        self.val = val

    def to_string(self):
        if not bool(self.val["has"]):
            return "none"
        return self.val["value"]


class MapPrinter:
    """{K: V}: its keys and values, in the order they were added"""

    def __init__(self, val):
        self.keys = ArrayPrinter(val["keys"])
        self.vals = ArrayPrinter(val["vals"])
        # (entries removed since the map was last compacted: still there, marked gone)
        self.gone = [bool(int(g)) for _, g in ArrayPrinter(val["gone"]).children()]

    def to_string(self):
        return "{}" if self.keys._len() == len([g for g in self.gone if g]) else None

    def children(self):
        for i, ((_, k), (_, v)) in enumerate(zip(self.keys.children(), self.vals.children())):
            if i < len(self.gone) and self.gone[i]:
                continue
            yield "key", k
            yield "value", v

    def display_hint(self):
        return "map"


class EnumPrinter:
    """an enum with fields: its variant, and that variant's fields"""

    def __init__(self, val):
        self.val = val
        self.tag = str(val["tag"])

    def to_string(self):
        return self.tag

    def children(self):
        t = self.val.type.strip_typedefs()
        if any(f.name == self.tag for f in t.fields()):
            v = self.val[self.tag]
            for f in v.type.strip_typedefs().fields():
                yield f.name, v[f.name]


def lookup(val):
    name = val.type.name or val.type.strip_typedefs().name or ""
    if name == "str":
        return StrPrinter(val)
    if name.endswith("[]") and val.type.strip_typedefs().code == gdb.TYPE_CODE_PTR:
        return ArrayPrinter(val)
    t = val.type.strip_typedefs()
    if t.code != gdb.TYPE_CODE_STRUCT:
        return None
    if name.endswith("?"):
        return OptPrinter(val)
    fields = [f.name for f in t.fields()]
    if fields == ["keys", "vals", "slots", "hashes", "gone", "ngone"]:
        return MapPrinter(val)
    if fields[:1] == ["tag"] and t.fields()[0].type.strip_typedefs().code == gdb.TYPE_CODE_ENUM:
        return EnumPrinter(val)
    return None


gdb.pretty_printers.append(lookup)
