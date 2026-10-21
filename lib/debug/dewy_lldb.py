# lldb formatters for Dewy programs built with `dewy build -g`: every value shows as
# Dewy prints it inside a container (`"{[value]}"`): a string quoted, an array
# or record as its literal, an optional or union as its value, an `int` as its
# number (word or BigInt). Load them with
#     lldb -o "command script import <dewy>/lib/debug/dewy_lldb.py" ./program
# (or put that command in ~/.lldbinit; CodeLLDB in VS Code: "initCommands").
#
# A string or an array is a pointer to [rc][len][cap][data...] (null: empty); an
# optional `T?` is its value followed by a flag; a field whose type holds the
# record it is in (next: Node?) is a pointer to [rc][value] (null: none). An
# `int` is a word: even, the value shifted left one bit; odd, one more than the
# address of a one-element BigInt array header ([sign:int64 limbs:array<uint64>],
# each limb 32 bits of the magnitude, least significant first).
import lldb

LIMIT = 200         # elements shown of a long array
TEXT_LIMIT = 10000  # bytes shown of a long string
DATA = 24           # where the elements start, after rc, len and cap
MASK = (1 << 64) - 1
DEPTH = 16          # nesting shown before `…`


def _word(process, address):
    err = lldb.SBError()
    w = process.ReadUnsignedFromMemory(address, 8, err)
    if not err.Success():
        raise ValueError("unreadable memory")
    return w


def _signed(w):
    return w - (1 << 64) if w >> 63 else w


def _length(process, pointer):
    if pointer == 0:
        return 0
    n = _signed(_word(process, pointer + 8))
    return n if 0 < n < (1 << 40) else 0


def _text(process, pointer):
    n = _length(process, pointer)
    if n == 0:
        return '""'
    err = lldb.SBError()
    raw = process.ReadMemory(pointer + DATA, min(n, TEXT_LIMIT), err)
    if not err.Success():
        return "<unreadable>"
    text = raw.decode("utf-8", "replace").replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return '"' + text + ('..."' if n > TEXT_LIMIT else '"')


def tagged_int(process, word):
    """the value of an `int` word"""
    if word & 1 == 0:
        return _signed(word) >> 1
    big = ((word - 1) & MASK) + DATA
    sign = _signed(_word(process, big))
    limbs = _word(process, big + 8)
    value = 0
    for i in range(_length(process, limbs)):
        value += _word(process, limbs + DATA + 8 * i) << (32 * i)
    return -value if sign < 0 else value


def _fields(t):
    return [t.GetFieldAtIndex(i).GetName() for i in range(t.GetNumberOfFields())]


def _element_type(t):
    """an array pointer's element type, from its header's flexible data member"""
    header = t.GetCanonicalType().GetPointeeType()
    for i in range(header.GetNumberOfFields()):
        f = header.GetFieldAtIndex(i)
        if f.GetName() == "data":
            return f.GetType().GetArrayElementType()
    return None


def _array(v, pointer, elem, depth):
    process = v.GetProcess()
    n = _length(process, pointer)
    if n == 0 or elem is None or not elem.IsValid():
        return "[]"
    shown = min(n, LIMIT)
    size = elem.GetByteSize()
    items = [show(v.CreateValueFromAddress("[%d]" % i, pointer + DATA + i * size, elem), depth + 1) for i in range(shown)]
    return "[" + " ".join(items) + (" …" if n > shown else "") + "]"


def show(v, depth=0):
    """a value as Dewy text"""
    if depth > DEPTH:
        return "…"
    v = v.GetNonSyntheticValue()
    t = v.GetType()
    name = t.GetName() or ""
    c = t.GetCanonicalType()
    process = v.GetProcess()
    if name == "int" and c.GetTypeClass() == lldb.eTypeClassBuiltin:
        return str(tagged_int(process, v.GetValueAsUnsigned(0)))
    if name == "string":
        return _text(process, v.GetValueAsUnsigned(0))
    if c.IsPointerType():
        target = c.GetPointeeType()
        tname = target.GetName() or ""
        pointer = v.GetValueAsUnsigned(0)
        if tname.endswith(" box"):
            if pointer == 0:
                return "none"
            inner = target.GetFieldAtIndex(1).GetType()
            return show(v.CreateValueFromAddress("value", pointer + 8, inner), depth + 1)
        if tname.endswith(" header") or name.startswith("array<"):
            return _array(v, pointer, _element_type(t), depth)
        return v.GetValue() or ""
    if c.GetTypeClass() == lldb.eTypeClassBuiltin:
        if c.GetBasicType() == lldb.eBasicTypeBool:
            return "true" if v.GetValueAsUnsigned(0) else "false"
        return v.GetValue() or ""
    if c.GetTypeClass() == lldb.eTypeClassEnumeration:
        return v.GetValue() or ""
    if c.GetTypeClass() == lldb.eTypeClassArray:
        return "[" + " ".join(show(v.GetChildAtIndex(i), depth + 1) for i in range(v.GetNumChildren())) + "]"
    if not c.IsAggregateType():
        return v.GetValue() or ""
    fields = _fields(c)
    if fields == ["value", "has"] and name.endswith("?"):
        has = v.GetChildMemberWithName("has").GetValueAsUnsigned(0)
        return show(v.GetChildMemberWithName("value"), depth + 1) if has else "none"
    if fields == ["__keys", "vals", "slots", "hashes", "gone", "ngone"]:
        return _dict(v, depth)
    if fields[:1] == ["tag"] and c.GetFieldAtIndex(0).GetType().GetCanonicalType().GetTypeClass() == lldb.eTypeClassEnumeration:
        tag = v.GetChildMemberWithName("tag").GetValue() or ""
        if tag not in fields:
            return tag
        member = v.GetChildMemberWithName(tag)
        if _fields(member.GetType().GetCanonicalType()) == ["0"]:
            return show(member.GetChildMemberWithName("0"), depth + 1)
        return tag + _record(member, depth)
    return _record(v, depth)


def _record(v, depth):
    c = v.GetType().GetCanonicalType()
    parts = []
    for i in range(c.GetNumberOfFields()):
        f = c.GetFieldAtIndex(i).GetName()
        if f:
            parts.append("%s=%s" % (f, show(v.GetChildMemberWithName(f), depth + 1)))
    return "[" + " ".join(parts) + "]"


def _dict(v, depth):
    process = v.GetProcess()
    keys = v.GetChildMemberWithName("__keys")
    values = v.GetChildMemberWithName("vals")
    gone = v.GetChildMemberWithName("gone").GetValueAsUnsigned(0)
    key_type, value_type = _element_type(keys.GetType()), _element_type(values.GetType())
    kp, vp = keys.GetValueAsUnsigned(0), values.GetValueAsUnsigned(0)
    entries = []
    err = lldb.SBError()
    for i in range(min(_length(process, kp), LIMIT)):
        if gone and i < _length(process, gone) and process.ReadUnsignedFromMemory(gone + DATA + i, 1, err) != 0:
            continue
        k = v.CreateValueFromAddress("key", kp + DATA + i * key_type.GetByteSize(), key_type)
        x = v.CreateValueFromAddress("value", vp + DATA + i * value_type.GetByteSize(), value_type)
        entries.append("%s -> %s" % (show(k, depth + 1), show(x, depth + 1)))
    return "[" + " ".join(entries) + "]" if entries else "[->]"


def dewy_summary(valobj, internal_dict):
    try:
        return show(valobj)
    except (ValueError, TypeError) as error:
        return "<unreadable: %s>" % error


class NoChildren:
    """the summary is the whole value"""

    def __init__(self, valobj, internal_dict):
        pass

    def update(self):
        return False

    def num_children(self):
        return 0

    def get_child_index(self, name):
        return -1

    def get_child_at_index(self, i):
        return None

    def has_children(self):
        return False


def _is_dewy(t, internal_dict):
    """a record, optional, union or dictionary (not an array or string header)"""
    c = t.GetCanonicalType()
    name = t.GetName() or ""
    if c.IsPointerType():
        return (c.GetPointeeType().GetName() or "").endswith(" box")
    return c.IsAggregateType() and c.GetTypeClass() != lldb.eTypeClassArray and \
        not name.endswith(" header") and not name.endswith(" box")


def __lldb_init_module(debugger, internal_dict):
    m = __name__
    run = debugger.HandleCommand
    for pattern in ("^int$", "^string$", "^array<.+>$"):
        run('type summary add -w dewy -v -x "%s" -F %s.dewy_summary' % (pattern, m))
        run('type synthetic add -w dewy -x "%s" -l %s.NoChildren' % (pattern, m))
    # records, optionals, unions and dictionaries by what they hold: an lldb with
    # recognizer functions (else they show field by field)
    ci = debugger.GetCommandInterpreter()
    res = lldb.SBCommandReturnObject()
    ci.HandleCommand("type summary add -w dewy -v --recognizer-function %s._is_dewy -F %s.dewy_summary" % (m, m), res)
    if res.Succeeded():
        run("type synthetic add -w dewy --recognizer-function %s._is_dewy -l %s.NoChildren" % (m, m))
    run("type category enable dewy")
