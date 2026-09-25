"""µDewy bytecode: a recorder and a player for the parser's backend calls.

See udewy/BYTECODE.md. The recorder wraps a backend and writes each call the
parser makes before forwarding it. The player decodes a stream and makes the
same calls on a live backend, mapping each stream id to the id that backend
returns, one table per id space. Stream ids are dense per space in creation
order, so this recorder and the native one (udewy/bootstrap/stream.udewy)
write the same stream for one program.
"""
from __future__ import annotations

from pathlib import Path

from . import t1

MAGIC = b'UBC1'
SV_INT, SV_FUNCTION, SV_STRING, SV_STATIC = 1, 2, 3, 4

OPS = {
    'begin_module': 1, 'finish_module': 2, 'set_module_init': 3, 'set_imported_sources': 4,
    'mark_location': 5, 'note_local': 6, 'begin_scope': 7, 'end_scope': 8, 'intern_string': 9,
    'define_global': 10, 'declare_extern_global': 11, 'intern_static': 12, 'intern_words': 13,
    'push_string_ref': 14, 'push_global_ref': 15, 'push_static_ref': 16, 'load_global': 17,
    'store_global': 18, 'declare_function': 19, 'bind_extern_function': 20,
    'declare_extern_function': 21, 'begin_function': 22, 'end_function': 23,
    'set_reachable_functions': 24, 'load_param': 25, 'alloc_local': 26, 'load_local': 27,
    'store_local': 28, 'push_const_i64': 29, 'push_void': 30, 'push_fn_ref': 31, 'pop_value': 32,
    'save_value': 33, 'restore_value': 34, 'unary_op': 35, 'binary_op': 36, 'binary_immediate': 37,
    'begin_if': 38, 'begin_else': 39, 'end_if': 40, 'begin_loop': 41, 'begin_loop_body': 42,
    'end_loop': 43, 'emit_break': 44, 'emit_continue': 45, 'cond_and_split': 46,
    'cond_and_join': 47, 'cond_or_split': 48, 'cond_or_join': 49, 'emit_return': 50,
    'call_direct': 51, 'call_indirect': 52, 'emit_intrinsic': 53,
}
NAMES = {code: name for name, code in OPS.items()}
# Operations with no operands and no result: forwarded as they are.
PLAIN = {'begin_module', 'begin_scope', 'end_scope', 'end_function', 'push_void', 'pop_value',
         'save_value', 'restore_value', 'begin_if', 'begin_else', 'end_if', 'begin_loop',
         'begin_loop_body', 'end_loop', 'emit_break', 'emit_continue', 'emit_return'}
SPACES = ('function', 'global', 'string', 'static', 'slot', 'split')


class _Writer:
    def __init__(self):
        self.out = bytearray(MAGIC)

    def u(self, value: int) -> None:
        value &= (1 << 64) - 1
        while True:
            low = value & 0x7F
            value >>= 7
            if value == 0:
                self.out.append(low)
                return
            self.out.append(low | 0x80)

    def s(self, value: int) -> None:
        value &= (1 << 64) - 1
        signed = value - (1 << 64) if value >= 1 << 63 else value
        self.u(((signed << 1) ^ (signed >> 63)) & ((1 << 64) - 1))

    def raw(self, data: bytes) -> None:
        self.u(len(data))
        self.out.extend(data)

    def text(self, value: str) -> None:
        self.raw(value.encode())

    def optional(self, value: str | None) -> None:
        if value is None:
            self.u(0)
            return
        data = value.encode()
        self.u(len(data) + 1)
        self.out.extend(data)


class _Reference:
    """A backend reference value remembering the stream label behind it."""
    stream_kind: int
    stream_label: int


class _ReferenceText(str, _Reference):
    pass


class _ReferenceInt(int, _Reference):
    pass


def _reference(value, kind: int, label: int):
    wrapped = (_ReferenceText if isinstance(value, str) else _ReferenceInt)(value)
    wrapped.stream_kind = kind
    wrapped.stream_label = label
    return wrapped


class Recorder:
    """A backend wrapper writing every call the parser makes (see BYTECODE.md)."""

    def __init__(self, backend, link_artifacts: list[str]):
        self._backend = backend
        self._writer = _Writer()
        self._writer.u(len(link_artifacts))
        for artifact in link_artifacts:
            self._writer.text(str(artifact))
        self._spaces: dict[str, dict] = {space: {} for space in SPACES}
        self._counts: dict[str, int] = {space: 0 for space in SPACES}

    def stream(self) -> bytes:
        return bytes(self._writer.out)

    def __getattr__(self, name):
        # Queries (is_intrinsic, max_call_args, ...) and attributes pass
        # through unrecorded: their answers already shaped the calls made.
        return getattr(self._backend, name)

    def __setattr__(self, name, value):
        if name.startswith('_'):
            object.__setattr__(self, name, value)
        else:
            setattr(self._backend, name, value)

    # -- ids ----------------------------------------------------------------
    def _new(self, space: str, live) -> int:
        # A counter, not the table's size: live ids repeat (local slots
        # restart in every function) and a new one replaces the old entry.
        dense = self._counts[space]
        self._counts[space] = dense + 1
        self._spaces[space][live] = dense
        return dense

    def _id(self, space: str, live) -> int:
        return self._spaces[space][live]

    def _value(self, value) -> None:
        if isinstance(value, _Reference):
            space = {SV_FUNCTION: 'function', SV_STRING: 'string', SV_STATIC: 'static'}[value.stream_kind]
            self._writer.u(value.stream_kind)
            self._writer.u(self._id(space, value.stream_label))
            return
        self._writer.u(SV_INT)
        self._writer.s(int(value))

    def _op(self, name: str) -> None:
        self._writer.u(OPS[name])

    # -- references ---------------------------------------------------------
    def function_ref(self, label_id: int):
        return _reference(self._backend.function_ref(label_id), SV_FUNCTION, label_id)

    def string_ref(self, label_id: int):
        return _reference(self._backend.string_ref(label_id), SV_STRING, label_id)

    def static_ref(self, label_id: int):
        return _reference(self._backend.static_ref(label_id), SV_STATIC, label_id)

    # -- recorded operations -------------------------------------------------
    def finish_module(self) -> str:
        self._op('finish_module')
        return self._backend.finish_module()

    def set_module_init(self, name):
        self._op('set_module_init')
        self._writer.optional(name)
        return self._backend.set_module_init(name)

    def set_imported_sources(self, paths):
        self._op('set_imported_sources')
        self._writer.u(len(paths))
        for path in paths:
            self._writer.text(str(path))
        return self._backend.set_imported_sources(paths)

    def mark_location(self, path, line, column):
        self._op('mark_location')
        self._writer.text(str(path))
        self._writer.u(line)
        self._writer.u(column)
        return self._backend.mark_location(path, line, column)

    def note_local(self, slot, name, type_name, formatter=None, *, parameter=False):
        self._op('note_local')
        self._writer.u(self._id('slot', slot))
        self._writer.text(name)
        self._writer.text(type_name)
        self._writer.optional(formatter)
        self._writer.u(1 if parameter else 0)
        return self._backend.note_local(slot, name, type_name, formatter, parameter=parameter)

    def intern_string(self, content: bytes):
        self._op('intern_string')
        self._writer.raw(bytes(content))
        label = self._backend.intern_string(content)
        self._writer.u(self._new('string', label))
        return label

    def define_global(self, name, value):
        self._op('define_global')
        self._writer.optional(name)
        self._value(value)
        label = self._backend.define_global(name, value)
        self._writer.u(self._new('global', label))
        return label

    def declare_extern_global(self, name):
        self._op('declare_extern_global')
        self._writer.text(name)
        label = self._backend.declare_extern_global(name)
        self._writer.u(self._new('global', label))
        return label

    def intern_static(self, size):
        self._op('intern_static')
        self._writer.u(size)
        label = self._backend.intern_static(size)
        self._writer.u(self._new('static', label))
        return label

    def intern_words(self, elements):
        self._op('intern_words')
        self._writer.u(len(elements))
        for element in elements:
            self._value(element)
        label = self._backend.intern_words(elements)
        self._writer.u(self._new('static', label))
        return label

    def _label_op(self, name, space, label):
        self._op(name)
        self._writer.u(self._id(space, label))
        return getattr(self._backend, name)(label)

    def push_string_ref(self, label_id):
        return self._label_op('push_string_ref', 'string', label_id)

    def push_global_ref(self, label_id):
        return self._label_op('push_global_ref', 'global', label_id)

    def push_static_ref(self, label_id):
        return self._label_op('push_static_ref', 'static', label_id)

    def load_global(self, label_id):
        return self._label_op('load_global', 'global', label_id)

    def store_global(self, label_id):
        return self._label_op('store_global', 'global', label_id)

    def push_fn_ref(self, label_id):
        return self._label_op('push_fn_ref', 'function', label_id)

    def load_local(self, slot):
        return self._label_op('load_local', 'slot', slot)

    def store_local(self, slot):
        return self._label_op('store_local', 'slot', slot)

    def cond_and_join(self, label):
        return self._label_op('cond_and_join', 'split', label)

    def cond_or_join(self, label):
        return self._label_op('cond_or_join', 'split', label)

    def declare_function(self, name, num_params):
        self._op('declare_function')
        self._writer.optional(name)
        self._writer.u(num_params)
        label = self._backend.declare_function(name, num_params)
        self._writer.u(self._new('function', label))
        return label

    def bind_extern_function(self, label_id, name):
        self._op('bind_extern_function')
        self._writer.u(self._id('function', label_id))
        self._writer.text(name)
        return self._backend.bind_extern_function(label_id, name)

    def declare_extern_function(self, name, num_params):
        self._op('declare_extern_function')
        self._writer.text(name)
        self._writer.u(num_params)
        label = self._backend.declare_extern_function(name, num_params)
        self._writer.u(self._new('function', label))
        return label

    def begin_function(self, label_id, name, param_count, is_main):
        self._op('begin_function')
        self._writer.u(self._id('function', label_id))
        self._writer.optional(name)
        self._writer.u(param_count)
        self._writer.u(1 if is_main else 0)
        return self._backend.begin_function(label_id, name, param_count, is_main)

    def set_reachable_functions(self, label_ids):
        self._op('set_reachable_functions')
        ids = sorted(self._id('function', label) for label in label_ids)
        self._writer.u(len(ids))
        for dense in ids:
            self._writer.u(dense)
        return self._backend.set_reachable_functions(label_ids)

    def load_param(self, index):
        self._op('load_param')
        self._writer.u(index)
        return self._backend.load_param(index)

    def alloc_local(self):
        self._op('alloc_local')
        slot = self._backend.alloc_local()
        self._writer.u(self._new('slot', slot))
        return slot

    def push_const_i64(self, value):
        self._op('push_const_i64')
        self._writer.s(value)
        return self._backend.push_const_i64(value)

    def unary_op(self, op_kind):
        self._op('unary_op')
        self._writer.u(int(op_kind.value))
        return self._backend.unary_op(op_kind)

    def binary_op(self, op_kind):
        self._op('binary_op')
        self._writer.u(int(op_kind.value))
        return self._backend.binary_op(op_kind)

    def binary_immediate(self, op_kind, value):
        self._op('binary_immediate')
        self._writer.u(int(op_kind.value))
        self._writer.s(value)
        return self._backend.binary_immediate(op_kind, value)

    def cond_and_split(self):
        self._op('cond_and_split')
        label = self._backend.cond_and_split()
        self._writer.u(self._new('split', label))
        return label

    def cond_or_split(self):
        self._op('cond_or_split')
        label = self._backend.cond_or_split()
        self._writer.u(self._new('split', label))
        return label

    def call_direct(self, label_id, num_args):
        self._op('call_direct')
        self._writer.u(self._id('function', label_id))
        self._writer.u(num_args)
        return self._backend.call_direct(label_id, num_args)

    def call_indirect(self, num_args):
        self._op('call_indirect')
        self._writer.u(num_args)
        return self._backend.call_indirect(num_args)

    def emit_intrinsic(self, name, num_args, intrinsic_data=None):
        self._op('emit_intrinsic')
        self._writer.text(name)
        self._writer.u(num_args)
        static_args = (intrinsic_data or {}).get('static_args', {})
        self._writer.u(len(static_args))
        for index in sorted(static_args):
            self._writer.u(index)
            self._writer.s(static_args[index])
        return self._backend.emit_intrinsic(name, num_args, intrinsic_data)


def _plain(name):
    def forward(self):
        self._op(name)
        return getattr(self._backend, name)()
    forward.__name__ = name
    return forward


for _name in PLAIN:
    setattr(Recorder, _name, _plain(_name))


class _Reader:
    def __init__(self, data: bytes):
        if data[:4] != MAGIC:
            raise ValueError('not a UBC1 stream')
        self.data = data
        self.at = 4

    def u(self) -> int:
        value = 0
        shift = 0
        while True:
            if self.at >= len(self.data):
                raise ValueError('truncated µDewy bytecode stream')
            byte = self.data[self.at]
            self.at += 1
            value |= (byte & 0x7F) << shift
            if not byte & 0x80:
                return value & ((1 << 64) - 1)
            shift += 7

    def s(self) -> int:
        z = self.u()
        value = (z >> 1) ^ -(z & 1)
        return value - (1 << 64) if value >= 1 << 63 else value

    def raw(self) -> bytes:
        count = self.u()
        data = self.data[self.at:self.at + count]
        if len(data) != count:
            raise ValueError('truncated µDewy bytecode stream')
        self.at += count
        return data

    def text(self) -> str:
        return self.raw().decode()

    def optional(self) -> str | None:
        count = self.u()
        if count == 0:
            return None
        data = self.data[self.at:self.at + count - 1]
        self.at += count - 1
        return data.decode()


class Stream:
    """A decoded stream header; `play` replays the operations into a backend."""

    def __init__(self, data: bytes):
        self._reader = _Reader(data)
        self.link_artifacts = [self._reader.text() for _ in range(self._reader.u())]
        self.imported_sources: list[Path] = []

    def play(self, backend) -> str:
        read = self._reader
        spaces: dict[str, dict[int, object]] = {space: {} for space in SPACES}

        def create(space: str, live) -> None:
            spaces[space][read.u()] = live

        def live(space: str):
            return spaces[space][read.u()]

        def value():
            kind = read.u()
            if kind == SV_INT:
                return read.s()
            label = read.u()
            if kind == SV_FUNCTION:
                return backend.function_ref(spaces['function'][label])
            if kind == SV_STRING:
                return backend.string_ref(spaces['string'][label])
            if kind == SV_STATIC:
                return backend.static_ref(spaces['static'][label])
            raise ValueError(f'unknown stable value kind {kind}')

        while True:
            name = NAMES.get(read.u())
            if name is None:
                raise ValueError('unknown µDewy bytecode operation')
            if name in PLAIN:
                getattr(backend, name)()
            elif name == 'finish_module':
                return backend.finish_module()
            elif name == 'set_module_init':
                backend.set_module_init(read.optional())
            elif name == 'set_imported_sources':
                self.imported_sources = [Path(read.text()) for _ in range(read.u())]
                backend.set_imported_sources(self.imported_sources)
            elif name == 'mark_location':
                backend.mark_location(read.text(), read.u(), read.u())
            elif name == 'note_local':
                slot, local_name, type_name, formatter = live('slot'), read.text(), read.text(), read.optional()
                backend.note_local(slot, local_name, type_name, formatter, parameter=read.u() != 0)
            elif name == 'intern_string':
                create('string', backend.intern_string(read.raw()))
            elif name == 'define_global':
                global_name = read.optional()
                create('global', backend.define_global(global_name, value()))
            elif name == 'declare_extern_global':
                create('global', backend.declare_extern_global(read.text()))
            elif name == 'intern_static':
                create('static', backend.intern_static(read.u()))
            elif name == 'intern_words':
                elements = [value() for _ in range(read.u())]
                create('static', backend.intern_words(elements))
            elif name in ('push_string_ref', 'push_global_ref', 'push_static_ref', 'load_global', 'store_global',
                          'push_fn_ref', 'load_local', 'store_local', 'cond_and_join', 'cond_or_join'):
                space = {'push_string_ref': 'string', 'push_static_ref': 'static', 'push_fn_ref': 'function',
                         'load_local': 'slot', 'store_local': 'slot', 'cond_and_join': 'split',
                         'cond_or_join': 'split'}.get(name, 'global')
                getattr(backend, name)(live(space))
            elif name == 'declare_function':
                function_name = read.optional()
                create('function', backend.declare_function(function_name, read.u()))
            elif name == 'bind_extern_function':
                label = live('function')
                backend.bind_extern_function(label, read.text())
            elif name == 'declare_extern_function':
                function_name = read.text()
                create('function', backend.declare_extern_function(function_name, read.u()))
            elif name == 'begin_function':
                label, function_name, count = live('function'), read.optional(), read.u()
                backend.begin_function(label, function_name, count, read.u() != 0)
            elif name == 'set_reachable_functions':
                backend.set_reachable_functions({live('function') for _ in range(read.u())})
            elif name == 'load_param':
                backend.load_param(read.u())
            elif name == 'alloc_local':
                create('slot', backend.alloc_local())
            elif name == 'push_const_i64':
                backend.push_const_i64(read.s())
            elif name == 'unary_op':
                backend.unary_op(t1.Kind(read.u()))
            elif name == 'binary_op':
                backend.binary_op(t1.Kind(read.u()))
            elif name == 'binary_immediate':
                kind = t1.Kind(read.u())
                backend.binary_immediate(kind, read.s())
            elif name in ('cond_and_split', 'cond_or_split'):
                create('split', getattr(backend, name)())
            elif name == 'call_direct':
                label = live('function')
                backend.call_direct(label, read.u())
            elif name == 'call_indirect':
                backend.call_indirect(read.u())
            elif name == 'emit_intrinsic':
                intrinsic, count = read.text(), read.u()
                static_args = {}
                for _ in range(read.u()):
                    index = read.u()
                    static_args[index] = read.s()
                backend.emit_intrinsic(intrinsic, count, {'static_args': static_args} if static_args else None)
            else:
                raise ValueError(f'µDewy bytecode operation {name} is not handled')
