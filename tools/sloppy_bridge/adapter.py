"""Experimental checked µDewy stream -> Sloppy register IR (Linux x86-64).

No Dewy parsing, inference or ownership rules live here. The existing compiler
has already checked and lowered those, including its runtime, into the stream.
Unsupported operations raise; this adapter never falls back to another backend.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

from udewy import t1
from udewy.backend.common import wrap_i64

# This is our wire enumeration, not Sloppy's internal enum numbering.
OPS = ('iconst mov add sub mul divs divu rems remu and_ or_ xor shl shrs shru '
       'neg not_ eq ne lts les gts ges ltu leu gtu geu load store slot gaddr '
       'daddr faddr call calli syscall block loop if_ else_ end br brif ret trap intr').split()


@dataclass
class Function:
    name: str
    params: int
    registers: int = 0
    slots: list[int] = field(default_factory=list)
    code: list[tuple] = field(default_factory=list)
    args: list[int] = field(default_factory=list)
    constants: dict[int, int] = field(default_factory=dict)


class Adapter:
    bytecode_target = 'x86_64'

    def __init__(self):
        self.functions: list[Function | None] = []
        self.names: list[str] = []
        self.data_size = 8  # Sloppy entry stores initial rsp at offset zero.
        self.rodata = bytearray()
        self.initializers: list[tuple[int, int | tuple]] = []
        self.module_init = None
        self.main = None
        self.reachable = None
        self.fn = None

    def begin_module(self): pass
    def set_imported_sources(self, paths): pass
    def mark_location(self, path, line, column): pass
    def note_local(self, *args, **kwargs): pass
    def begin_scope(self): pass
    def end_scope(self): pass

    def reg(self):
        r = self.fn.registers
        self.fn.registers += 1
        return r

    def emit(self, op, dst=-1, a=0, b=0, c=0, imm=0):
        self.fn.code.append((OPS.index(op), dst, a, b, c, wrap_i64(imm)))

    def value(self, op, a=0, b=0, c=0, imm=0):
        r = self.reg()
        self.emit(op, r, a, b, c, imm)
        return r

    def constant(self, n):
        r = self.value('iconst', imm=n)
        self.fn.constants[r] = wrap_i64(n)
        return r

    def reserve(self, size):
        at = (self.data_size + 7) & ~7
        self.data_size = at + max(size, 1)
        return at

    def intern_string(self, content):
        while len(self.rodata) % 8: self.rodata.append(0)
        self.rodata.extend(struct.pack('<Q', len(content)))
        at = len(self.rodata)
        self.rodata.extend(content)
        self.rodata.append(0)
        return at

    def intern_static(self, size): return self.reserve(size)

    def intern_words(self, elements):
        at = self.reserve(len(elements) * 8)
        self.initializers.extend((at + i * 8, v) for i, v in enumerate(elements))
        return at

    def define_global(self, name, value):
        return self.intern_words([value])

    def declare_extern_global(self, name):
        raise ValueError(f'Sloppy bridge: external global {name!r} is unsupported')

    def bind_extern_function(self, label_id, name):
        raise ValueError(f'Sloppy bridge: external function {name!r} is unsupported')

    def declare_extern_function(self, name, num_params):
        self.bind_extern_function(-1, name)

    def function_ref(self, label_id): return ('faddr', label_id)
    def string_ref(self, label_id): return ('daddr', label_id)
    def static_ref(self, label_id): return ('gaddr', label_id)

    def stable(self, value):
        if isinstance(value, int): return self.constant(value)
        return self.value(value[0], imm=value[1])

    def push_string_ref(self, label_id): self.current = self.value('daddr', imm=label_id)
    def push_static_ref(self, label_id): self.current = self.value('gaddr', imm=label_id)
    def push_global_ref(self, label_id): self.push_static_ref(label_id)
    def push_fn_ref(self, label_id): self.current = self.value('faddr', imm=label_id)

    def load_global(self, label_id):
        self.current = self.value('load', self.value('gaddr', imm=label_id), c=8)

    def store_global(self, label_id):
        self.emit('store', a=self.value('gaddr', imm=label_id), b=self.current, c=8)

    def declare_function(self, name, num_params):
        label = len(self.functions)
        self.functions.append(None)
        self.names.append(name or f'function_{label}')
        return label

    def begin_function(self, label_id, name, param_count, is_main):
        self.fn = Function(name or self.names[label_id], param_count, param_count)
        self.functions[label_id] = self.fn
        self.saved = []
        self.control = []
        self.current = self.constant(0)
        if is_main: self.main = label_id

    def end_function(self):
        if self.control or self.saved:
            raise ValueError('Sloppy bridge: unbalanced function state')
        # µDewy's implicit return is zero, including an empty function.
        self.emit('ret', a=self.constant(0))
        self.fn = None

    def set_reachable_functions(self, label_ids): self.reachable = label_ids
    def set_module_init(self, name): self.module_init = name
    def load_param(self, index): self.current = self.value('mov', index)
    def alloc_local(self): return self.reg()
    def load_local(self, slot): self.current = self.value('mov', slot)
    def store_local(self, slot): self.emit('mov', slot, self.current)
    def push_const_i64(self, value): self.current = self.constant(value)
    def push_void(self): self.push_const_i64(0)
    def pop_value(self): pass
    def save_value(self): self.saved.append(self.current)
    def restore_value(self): self.current = self.saved.pop()

    def unary_op(self, op_kind):
        self.current = self.value({t1.Kind.TK_MINUS: 'neg', t1.Kind.TK_NOT: 'not_'}[op_kind], self.current)

    def binary(self, op, lhs, rhs):
        if op in ('divs', 'divu', 'rems', 'remu'):
            # µDewy defines zero divisors and MIN/-1; raw x86 division traps.
            # Guard these before entering Sloppy's ordinary division operation.
            result = self.reg()
            zero = self.constant(0)
            self.emit('if_', a=self.value('eq', rhs, zero))
            self.emit('mov', result, lhs if op.startswith('rem') else self.constant(-1))
            self.emit('else_')
            if op.endswith('s'):
                special = self.value('and_', self.value('eq', lhs, self.constant(-(1 << 63))),
                                     self.value('eq', rhs, self.constant(-1)))
                self.emit('if_', a=special)
                self.emit('mov', result, zero if op == 'rems' else lhs)
                self.emit('else_')
            self.emit('mov', result, self.value(op, lhs, rhs))
            if op.endswith('s'): self.emit('end')
            self.emit('end')
            return result
        result = self.value(op, lhs, rhs)
        if op in ('eq', 'ne', 'lts', 'les', 'gts', 'ges', 'ltu', 'leu', 'gtu', 'geu'):
            result = self.value('neg', result)  # Dewy true is all ones; Sloppy true is 1.
        return result

    def binary_op(self, op_kind):
        mapping = dict(zip((t1.Kind.TK_PLUS, t1.Kind.TK_MINUS, t1.Kind.TK_MUL,
                            t1.Kind.TK_IDIV, t1.Kind.TK_MOD, t1.Kind.TK_AND,
                            t1.Kind.TK_OR, t1.Kind.TK_XOR, t1.Kind.TK_LEFT_SHIFT,
                            t1.Kind.TK_RIGHT_SHIFT, t1.Kind.TK_EQ, t1.Kind.TK_NOT_EQ,
                            t1.Kind.TK_LT, t1.Kind.TK_LT_EQ, t1.Kind.TK_GT, t1.Kind.TK_GT_EQ),
                           ('add', 'sub', 'mul', 'divs', 'rems', 'and_', 'or_', 'xor',
                            'shl', 'shru', 'eq', 'ne', 'lts', 'les', 'gts', 'ges')))
        self.current = self.binary(mapping[op_kind], self.saved.pop(), self.current)

    def binary_immediate(self, op_kind, value):
        self.save_value()
        self.push_const_i64(value)
        self.binary_op(op_kind)

    def take_args(self, count):
        if count == 0: return []
        if count > len(self.saved): raise ValueError('Sloppy bridge: missing arguments')
        args = self.saved[-count:]
        del self.saved[-count:]
        return args

    def call(self, op, args, target=0, indirect=0):
        start = len(self.fn.args)
        self.fn.args.extend(args)
        return self.value(op, start, len(args), indirect, target)

    def call_direct(self, label_id, num_args):
        self.current = self.call('call', self.take_args(num_args), label_id)

    def call_indirect(self, num_args):
        target, *args = self.take_args(num_args + 1)
        self.current = self.call('calli', args, indirect=target)

    def begin_if(self):
        self.emit('if_', a=self.current)
        self.control.append('if')

    def begin_else(self): self.emit('else_')
    def end_if(self):
        assert self.control.pop() == 'if'
        self.emit('end')

    def begin_loop(self):
        self.emit('block')
        self.emit('loop')
        self.control.extend(('break', 'continue'))

    def branch(self, kind, condition=None):
        depth = self.control[::-1].index(kind)
        self.emit('br' if condition is None else 'brif', a=condition or 0, imm=depth)

    def begin_loop_body(self):
        self.branch('break', self.value('eq', self.current, self.constant(0)))

    def end_loop(self):
        self.branch('continue')
        assert self.control.pop() == 'continue'
        assert self.control.pop() == 'break'
        self.emit('end')
        self.emit('end')

    def emit_break(self): self.branch('break')
    def emit_continue(self): self.branch('continue')
    def emit_return(self): self.emit('ret', a=self.current)

    def cond_split(self, is_or):
        result = self.value('mov', self.current)
        if is_or: self.current = self.value('eq', self.current, self.constant(0))
        self.begin_if()
        return result

    def cond_and_split(self): return self.cond_split(False)
    def cond_or_split(self): return self.cond_split(True)
    def cond_and_join(self, result):
        self.emit('mov', result, self.current)
        self.end_if()
        self.current = result
    def cond_or_join(self, result): self.cond_and_join(result)

    def emit_intrinsic(self, name, num_args, intrinsic_data=None):
        args = [*self.take_args(num_args - 1), self.current] if num_args else []
        if name.startswith('__syscall'):
            if not 1 <= num_args <= 7: raise ValueError('invalid syscall arity')
            self.current = self.call('syscall', args)
        elif name.startswith(('__load_', '__store_')) or name in ('__load__', '__store__'):
            width = 8 if name in ('__load__', '__store__') else int(name.split('_')[-3][1:]) // 8
            if width not in (1, 2, 4, 8): raise ValueError(f'unsupported width: {name}')
            if name.startswith('__load'):
                self.current = self.value('load', args[0], c=width | (16 if '_i' in name else 0))
            else:
                self.emit('store', a=args[1], b=args[0], c=width)
                self.push_void()
        elif name == '__alloca__':
            # A fresh allocation on *every execution*, including in loops.
            # A Sloppy frame slot would silently alias repeated allocations.
            self.current = self.call('intr', args, target=1000)
        elif name in ('__signed_shr__', '__unsigned_idiv__', '__unsigned_mod__',
                      '__unsigned_lt__', '__unsigned_lte__', '__unsigned_gt__', '__unsigned_gte__'):
            op = dict(zip(('__signed_shr__', '__unsigned_idiv__', '__unsigned_mod__',
                           '__unsigned_lt__', '__unsigned_lte__', '__unsigned_gt__', '__unsigned_gte__'),
                          ('shrs', 'divu', 'remu', 'ltu', 'leu', 'gtu', 'geu')))[name]
            self.current = self.binary(op, *args)
        else:
            raise ValueError(f'Sloppy bridge: intrinsic {name!r} is unsupported')

    def finish_module(self):
        init = self.declare_function('__bridge_init', 0)
        self.begin_function(init, '__bridge_init', 0, False)
        for at, value in self.initializers:
            self.emit('store', a=self.value('gaddr', imm=at), b=self.stable(value), c=8)
        if self.module_init is not None:
            self.call('call', [], self.names.index(self.module_init))
        self.end_function()
        wrapper = self.declare_function('__bridge_main', 0)
        self.begin_function(wrapper, '__bridge_main', 0, False)
        if self.main is not None:
            params = self.functions[self.main].params
            if params > 2: raise ValueError('Sloppy bridge: main takes more than argc/argv')
            sp = self.value('load', self.value('gaddr', imm=0), c=8)
            args = [self.value('load', sp, c=8), self.value('add', sp, self.constant(8))][:params]
            self.current = self.call('call', args, self.main)
            self.emit_return()
        self.end_function()
        out = bytearray(b'DWYSLP01')

        def word(n): out.extend(struct.pack('<q', wrap_i64(n)))
        def blob(data):
            word(len(data))
            out.extend(data)

        word(self.data_size)
        word(init)
        word(wrapper)
        blob(self.rodata)
        word(len(self.functions))
        for index, fn in enumerate(self.functions):
            if fn is None: raise ValueError(f'Sloppy bridge: undefined function {self.names[index]}')
            blob(fn.name.encode())
            word(fn.params)
            word(fn.registers)
            word(len(fn.slots))
            for size in fn.slots: word(size)
            word(len(fn.args))
            for arg in fn.args: word(arg)
            word(len(fn.code))
            for ins in fn.code:
                for part in ins: word(part)
        return bytes(out)
