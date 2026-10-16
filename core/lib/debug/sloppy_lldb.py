# lldb formatters for Sloppy programs built with `sloppy build -g`: strings as text, arrays and
# maps as their elements, optionals as their value or none, enums with fields as their variant.
# Load them with
#     lldb -o "command script import <sloppy>/lib/debug/sloppy_lldb.py" ./game
# (or put that command in ~/.lldbinit; CodeLLDB in VS Code: "initCommands").
#
# A string or an array is a pointer to [rc][len][cap][data...] (null: empty); an optional `T?` is
# its value followed by a flag.
import lldb

LIMIT = 200         # elements shown of a long array
TEXT_LIMIT = 10000  # bytes shown of a long string
DATA = 24           # where the elements start, after rc, len and cap


def _len(valobj):
    p = valobj.GetValueAsUnsigned(0)
    if p == 0:
        return 0
    err = lldb.SBError()
    n = valobj.GetProcess().ReadUnsignedFromMemory(p + 8, 8, err)
    return n if err.Success() and 0 < n < (1 << 40) else 0


def str_summary(valobj, internal_dict):
    v = valobj.GetNonSyntheticValue()
    n = _len(v)
    if n == 0:
        return '""'
    err = lldb.SBError()
    raw = v.GetProcess().ReadMemory(v.GetValueAsUnsigned() + DATA, min(n, TEXT_LIMIT), err)
    if not err.Success():
        return "<unreadable>"
    text = raw.decode("utf-8", "replace").replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return '"' + text + ('..."' if n > TEXT_LIMIT else '"')


class ArrayChildren:
    def __init__(self, valobj, internal_dict):
        self.valobj = valobj
        self.update()

    def update(self):
        self.n = min(_len(self.valobj), LIMIT)
        hdr = self.valobj.GetType().GetCanonicalType().GetPointeeType()
        data = hdr.GetFieldAtIndex(3).GetType() if hdr.GetNumberOfFields() > 3 else None
        self.elem = data.GetArrayElementType() if data is not None else None
        return False

    def num_children(self):
        return self.n if self.elem is not None else 0

    def get_child_index(self, name):
        try:
            return int(name.strip("[]"))
        except ValueError:
            return -1

    def get_child_at_index(self, i):
        if i < 0 or i >= self.n or self.elem is None:
            return None
        addr = self.valobj.GetValueAsUnsigned() + DATA + i * self.elem.GetByteSize()
        return self.valobj.CreateValueFromAddress("[%d]" % i, addr, self.elem)

    def has_children(self):
        return True


class NoChildren:
    """a string: its text, nothing to open"""

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


def array_summary(valobj, internal_dict):
    n = _len(valobj.GetNonSyntheticValue())
    return "%d elements" % n


class MapChildren:
    def __init__(self, valobj, internal_dict):
        self.valobj = valobj
        self.update()

    def update(self):
        v = self.valobj.GetNonSyntheticValue()
        self.keys = ArrayChildren(v.GetChildMemberWithName("keys"), None)
        self.vals = ArrayChildren(v.GetChildMemberWithName("vals"), None)
        # (entries removed since the map was last compacted: still there, marked gone)
        gone = ArrayChildren(v.GetChildMemberWithName("gone"), None)
        ng = gone.num_children()
        dead = set(i for i in range(ng) if (gone.get_child_at_index(i).GetValueAsUnsigned(0) or 0) != 0)
        n = min(self.keys.num_children(), self.vals.num_children())
        self.live = [i for i in range(n) if i not in dead]
        return False

    def num_children(self):
        return len(self.live)

    def get_child_index(self, name):
        return -1

    def get_child_at_index(self, j):
        if j < 0 or j >= len(self.live):
            return None
        i = self.live[j]
        k = self.keys.get_child_at_index(i)
        v = self.vals.get_child_at_index(i)
        if k is None or v is None:
            return None
        key = k.GetSummary() or k.GetValue() or "?"
        return v.CreateValueFromData("[%s]" % key, v.GetData(), v.GetType())

    def has_children(self):
        return True


def opt_summary(valobj, internal_dict):
    v = valobj.GetNonSyntheticValue()
    if not v.GetChildMemberWithName("has").GetValueAsUnsigned(0):
        return "none"
    x = v.GetChildMemberWithName("value")
    return x.GetSummary() or x.GetValue() or ""


class EnumChildren:
    """an enum with fields: the fields of the variant its tag says"""

    def __init__(self, valobj, internal_dict):
        self.valobj = valobj
        self.update()

    def update(self):
        v = self.valobj.GetNonSyntheticValue()
        tag = v.GetChildMemberWithName("tag").GetValue()
        self.variant = v.GetChildMemberWithName(tag) if tag else None
        return False

    def num_children(self):
        return self.variant.GetNumChildren() if self.variant and self.variant.IsValid() else 0

    def get_child_index(self, name):
        return self.variant.GetIndexOfChildWithName(name) if self.variant else -1

    def get_child_at_index(self, i):
        return self.variant.GetChildAtIndex(i) if self.variant else None

    def has_children(self):
        return True


def enum_summary(valobj, internal_dict):
    return valobj.GetNonSyntheticValue().GetChildMemberWithName("tag").GetValue() or ""


def _is_enum_with_fields(t, internal_dict):
    t = t.GetCanonicalType()
    return t.GetNumberOfFields() > 0 and t.GetFieldAtIndex(0).GetName() == "tag" and \
        t.GetFieldAtIndex(0).GetType().GetCanonicalType().GetTypeClass() == lldb.eTypeClassEnumeration


def _is_map(t, internal_dict):
    t = t.GetCanonicalType()
    return [t.GetFieldAtIndex(i).GetName() for i in range(t.GetNumberOfFields())] == ["keys", "vals", "slots", "hashes", "gone", "ngone"]


def __lldb_init_module(debugger, internal_dict):
    m = __name__
    run = debugger.HandleCommand
    run("type summary add -w sloppy -v -F %s.str_summary str" % m)
    run("type synthetic add -w sloppy -l %s.NoChildren str" % m)
    run('type synthetic add -w sloppy -x "\\[\\]$" -l %s.ArrayChildren' % m)
    run('type summary add -w sloppy -v -x "\\[\\]$" -F %s.array_summary' % m)
    run('type summary add -w sloppy -x "\\?$" -F %s.opt_summary' % m)
    # (maps by their type's name, {K: V})
    run('type synthetic add -w sloppy -x "^\\{.+: .+\\}$" -l %s.MapChildren' % m)
    # (Windows: the names in a PDB, compiler/pdb.jo: str *, array<T> *, optional<T>, Map<K, V>;
    # not checked by tools/dbgtest.py, which uses cdb there)
    run('type summary add -w sloppy -v -x "^str \\*$" -F %s.str_summary' % m)
    run('type synthetic add -w sloppy -x "^str \\*$" -l %s.NoChildren' % m)
    run('type synthetic add -w sloppy -x "^array<.+> \\*$" -l %s.ArrayChildren' % m)
    run('type summary add -w sloppy -v -x "^array<.+> \\*$" -F %s.array_summary' % m)
    run('type summary add -w sloppy -x "^optional<.+>$" -F %s.opt_summary' % m)
    run('type synthetic add -w sloppy -x "^Map<.+>$" -l %s.MapChildren' % m)
    # enums with fields by what they hold: an lldb with recognizer functions (else they show as
    # their tag and each variant's fields)
    ci = debugger.GetCommandInterpreter()
    res = lldb.SBCommandReturnObject()
    ci.HandleCommand("type synthetic add -w sloppy --recognizer-function %s._is_enum_with_fields -l %s.EnumChildren" % (m, m), res)
    if res.Succeeded():
        run("type summary add -w sloppy --recognizer-function %s._is_enum_with_fields -F %s.enum_summary" % (m, m))
    run("type category enable sloppy")
