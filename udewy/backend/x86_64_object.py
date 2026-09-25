"""x86-64 assembly text to an ELF relocatable object, without `as`.

The x86-64 backend emits a closed set of AT&T instructions and directives
(see ROADMAP "Direct binary fast path"). This encodes exactly that set: one
pass writes every instruction, local branches are always near (rel32) and are
patched once their labels are known, and every reference that leaves its
section becomes a relocation for `ld`. Debug builds add the DWARF the backend
spells as data (`.uleb128`, `.value`, `.string`, label differences resolved
once every label is placed) and `.file`/`.loc` rows, from which this writes
the `.debug_line` program an assembler would. Anything outside the set is an
error, never a guess. Mirrors `udewy/bootstrap/backend/x86_64_object.udewy`.
"""
from __future__ import annotations

import struct

from . import elf

R_X86_64_64 = 1
R_X86_64_PC32 = 2
R_X86_64_PLT32 = 4
R_X86_64_32 = 10

# The `.debug_line` header gas writes: DWARF 3, and its special-opcode space.
LINE_VERSION = 3
LINE_BASE = -5
LINE_RANGE = 14
OPCODE_BASE = 13
STANDARD_OPCODE_LENGTHS = bytes([0, 1, 1, 1, 1, 0, 0, 0, 1, 0, 0, 1])
DW_LNS_copy = 1
DW_LNS_advance_pc = 2
DW_LNS_advance_line = 3
DW_LNS_set_file = 4
DW_LNS_set_column = 5
DW_LNE_end_sequence = 1
DW_LNE_set_address = 2

REGISTERS_64 = {name: index for index, name in enumerate(
    ['rax', 'rcx', 'rdx', 'rbx', 'rsp', 'rbp', 'rsi', 'rdi', 'r8', 'r9', 'r10', 'r11', 'r12', 'r13', 'r14', 'r15'])}
REGISTERS_32 = {name: index for index, name in enumerate(
    ['eax', 'ecx', 'edx', 'ebx', 'esp', 'ebp', 'esi', 'edi', 'r8d', 'r9d', 'r10d', 'r11d', 'r12d', 'r13d', 'r14d', 'r15d'])}
REGISTERS_16 = {name: index for index, name in enumerate(
    ['ax', 'cx', 'dx', 'bx', 'sp', 'bp', 'si', 'di', 'r8w', 'r9w', 'r10w', 'r11w', 'r12w', 'r13w', 'r14w', 'r15w'])}
REGISTERS_XMM = {f'xmm{index}': index for index in range(16)}
REGISTERS_8 = {name: index for index, name in enumerate(
    ['al', 'cl', 'dl', 'bl', 'spl', 'bpl', 'sil', 'dil', 'r8b', 'r9b', 'r10b', 'r11b', 'r12b', 'r13b', 'r14b', 'r15b'])}

CONDITIONS = {'o': 0, 'no': 1, 'b': 2, 'c': 2, 'nae': 2, 'ae': 3, 'nb': 3, 'nc': 3, 'e': 4, 'z': 4, 'ne': 5, 'nz': 5,
              'be': 6, 'na': 6, 'a': 7, 'nbe': 7, 's': 8, 'ns': 9, 'p': 10, 'pe': 10, 'np': 11, 'po': 11,
              'l': 12, 'nge': 12, 'ge': 13, 'nl': 13, 'le': 14, 'ng': 14, 'g': 15, 'nle': 15}

# Two-operand integer ALU: (opcode r/m <- reg, opcode reg <- r/m, /digit of the immediate group).
ALU = {'add': (0x01, 0x03, 0), 'or': (0x09, 0x0B, 1), 'and': (0x21, 0x23, 4), 'sub': (0x29, 0x2B, 5),
       'xor': (0x31, 0x33, 6), 'cmp': (0x39, 0x3B, 7)}
UNARY = {'not': 2, 'neg': 3, 'div': 6, 'idiv': 7}
SHIFTS = {'shl': 4, 'sal': 4, 'shr': 5, 'sar': 7}
# SSE moves and conversions between a general register and an xmm one:
# (mandatory prefix, opcode, whether the xmm register is the ModRM reg field).
SSE = {'movd': (0x66, 0x6E, True), 'movq': (0x66, 0x6E, True), 'cvtsi2ss': (0xF3, 0x2A, True),
       'cvtsi2sd': (0xF2, 0x2A, True), 'cvttss2si': (0xF3, 0x2C, False), 'cvttsd2si': (0xF2, 0x2C, False)}
EXTENDS = {'movzbq': (0x0F, 0xB6), 'movzwq': (0x0F, 0xB7), 'movsbq': (0x0F, 0xBE), 'movswq': (0x0F, 0xBF)}


class AssemblyError(Exception):
    pass


class Register:
    __slots__ = ('index', 'width')

    def __init__(self, index: int, width: int):
        self.index = index
        self.width = width


class Memory:
    """`disp(base)` or `symbol+offset(%rip)`."""
    __slots__ = ('base', 'displacement', 'symbol')

    def __init__(self, base: int | None, displacement: int, symbol: str | None):
        self.base = base            # None: RIP-relative
        self.displacement = displacement
        self.symbol = symbol


class Immediate:
    __slots__ = ('value',)

    def __init__(self, value: int):
        self.value = value


def _integer(text: str) -> int:
    return int(text, 0)


def _symbol_offset(text: str) -> tuple[str, int]:
    """`name`, `name+8` or `name-8`."""
    for sign in ('+', '-'):
        at = text.rfind(sign, 1)
        if at > 0:
            tail = text[at + 1:]
            if tail and tail[0].isdigit():
                value = _integer(tail)
                return text[:at], value if sign == '+' else -value
    return text, 0


def _statements(raw: str) -> list[str]:
    """The statements on one line: `;` separates them and `#` starts a
    comment, outside string literals."""
    if '"' not in raw:
        if '#' in raw:
            raw = raw.split('#', 1)[0]
        return raw.split(';') if ';' in raw else [raw]
    statements: list[str] = []
    current: list[str] = []
    quoted = escaped = False
    for char in raw:
        if quoted:
            current.append(char)
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            current.append(char)
        elif char == '#':
            break
        elif char == ';':
            statements.append(''.join(current))
            current = []
        else:
            current.append(char)
    statements.append(''.join(current))
    return statements


def _string(text: str) -> bytes:
    """The bytes of a `"..."` literal (backslash escapes as gas reads them)."""
    text = text.strip()
    if len(text) < 2 or text[0] != '"' or text[-1] != '"':
        raise AssemblyError(f'expected a string literal, not {text}')
    out = bytearray()
    body = text[1:-1]
    at = 0
    while at < len(body):
        char = body[at]
        at += 1
        if char != '\\':
            out.extend(char.encode())
            continue
        escape = body[at]
        at += 1
        if escape in '01234567':
            digits = escape
            while len(digits) < 3 and at < len(body) and body[at] in '01234567':
                digits += body[at]
                at += 1
            out.append(int(digits, 8) & 0xFF)
        else:
            out.extend({'n': b'\n', 't': b'\t', 'r': b'\r', '\\': b'\\', '"': b'"'}[escape])
    return bytes(out)


def _uleb128(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _sleb128(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if (value == 0 and not byte & 0x40) or (value == -1 and byte & 0x40):
            out.append(byte)
            return bytes(out)
        out.append(byte | 0x80)


def _operand(text: str):
    text = text.strip()
    if text.startswith('%'):
        name = text[1:]
        for table, width in ((REGISTERS_64, 64), (REGISTERS_32, 32), (REGISTERS_16, 16), (REGISTERS_8, 8),
                             (REGISTERS_XMM, 128)):
            index = table.get(name)
            if index is not None:
                return Register(index, width)
        raise AssemblyError(f'unknown register {text}')
    if text.startswith('$'):
        return Immediate(_integer(text[1:]))
    if text.endswith(')'):
        open_at = text.index('(')
        base = text[open_at + 1:-1].strip()
        prefix = text[:open_at]
        if base == '%rip':
            symbol, offset = _symbol_offset(prefix)
            return Memory(None, offset, symbol)
        if not base.startswith('%') or base[1:] not in REGISTERS_64:
            raise AssemblyError(f'unsupported memory operand {text}')
        return Memory(REGISTERS_64[base[1:]], _integer(prefix) if prefix else 0, None)
    raise AssemblyError(f'unsupported operand {text}')


def _split_operands(text: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    start = 0
    for at, char in enumerate(text):
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        elif char == ',' and depth == 0:
            parts.append(text[start:at])
            start = at + 1
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def _fits8(value: int) -> bool:
    return -128 <= value <= 127


def _fits32(value: int) -> bool:
    return -2**31 <= value < 2**31


class Assembler:
    def __init__(self):
        self.object = elf.ObjectFile(elf.EM_X86_64)
        self.current = self.object.section('.text', elf.SHT_PROGBITS, elf.SHF_ALLOC | elf.SHF_EXECINSTR)
        self.object.section('.data', elf.SHT_PROGBITS, elf.SHF_ALLOC | elf.SHF_WRITE)
        self.object.section('.bss', elf.SHT_NOBITS, elf.SHF_ALLOC | elf.SHF_WRITE)
        # rel32 fields to resolve at the end: (section, offset of the field,
        # symbol, addend relative to the field, relocation kind).
        self.pending: list[tuple[int, int, str, int, int]] = []
        # Label differences in data, resolved at the end: (section, offset,
        # size, label, label subtracted).
        self.differences: list[tuple[int, int, int, str, str]] = []
        # `.file` names by number, and `.loc` rows per section (in the order
        # sections first get one): (offset, file, line, column). A `.loc`
        # waits for the instruction it describes.
        self.files: dict[int, str] = {}
        self.rows: dict[int, list[tuple[int, int, int, int]]] = {}
        self.loc: tuple[int, int, int] | None = None

    # -- output --------------------------------------------------------
    @property
    def data(self) -> bytearray:
        return self.object.sections[self.current].data

    def emit(self, *values: int) -> None:
        self.data.extend(values)

    def emit32(self, value: int) -> None:
        self.data.extend(struct.pack('<i', value))

    def rex(self, w: bool, reg: int, rm: int, byte_registers: tuple[Register, ...] = ()) -> None:
        value = 0x40 | (8 if w else 0) | (4 if reg & 8 else 0) | (1 if rm & 8 else 0)
        # spl, bpl, sil and dil exist only with a REX prefix.
        forced = any(operand.width == 8 and 4 <= operand.index <= 7 for operand in byte_registers)
        if value != 0x40 or forced:
            self.emit(value)

    def modrm(self, reg: int, operand: Register | Memory, trailing: int = 0) -> None:
        """ModRM (plus SIB and displacement) for `reg` and a register or memory operand.

        `trailing` is the number of immediate bytes after the displacement,
        which a RIP-relative displacement must account for.
        """
        if isinstance(operand, Register):
            self.emit(0xC0 | ((reg & 7) << 3) | (operand.index & 7))
            return
        if operand.base is None:
            self.emit(0x05 | ((reg & 7) << 3))
            # The CPU adds the displacement to the end of the instruction:
            # the field itself (4 bytes) and any immediate after it.
            self.reference(operand.symbol, operand.displacement - 4 - trailing, R_X86_64_PC32)
            return
        base = operand.base & 7
        displacement = operand.displacement
        if displacement == 0 and base != 5:
            mode = 0x00
        elif _fits8(displacement):
            mode = 0x40
        else:
            mode = 0x80
        self.emit(mode | ((reg & 7) << 3) | base)
        if base == 4:
            self.emit(0x24)          # SIB: no index, base rsp/r12
        if mode == 0x40:
            self.emit(displacement & 0xFF)
        elif mode == 0x80:
            self.emit32(displacement)

    def reference(self, symbol: str, addend: int, kind: int) -> None:
        """A rel32 field holding `symbol + addend - (address of the field)`."""
        offset = len(self.data)
        self.emit32(0)
        # Symbols enter the table at their first mention (as in the native
        # assembler), so both write identical objects.
        self.object.symbol(symbol)
        self.pending.append((self.current, offset, symbol, addend, kind))

    # -- directives -----------------------------------------------------
    def switch(self, name: str, flags_text: str = '', kind_text: str = '@progbits') -> None:
        flags = 0
        for letter in flags_text:
            flags |= elf.FLAG_LETTERS[letter]
        kind = elf.SHT_NOBITS if kind_text == '@nobits' else elf.SHT_PROGBITS
        self.current = self.object.section(name, kind, flags)

    def label(self, name: str) -> None:
        symbol = self.object.symbol(name)
        if symbol.section is not None:
            raise AssemblyError(f'label {name} defined twice')
        symbol.section = self.current
        symbol.value = self.object.sections[self.current].length()

    def directive(self, name: str, rest: str) -> None:
        section = self.object.sections[self.current]
        if name == '.text':
            self.current = self.object.section('.text')
        elif name == '.data':
            self.current = self.object.section('.data')
        elif name == '.bss':
            self.current = self.object.section('.bss')
        elif name == '.section':
            parts = [part.strip() for part in rest.split(',')]
            flags = parts[1].strip('"') if len(parts) > 1 else ''
            kind = parts[2] if len(parts) > 2 else '@progbits'
            self.switch(parts[0], flags, kind)
        elif name == '.globl' or name == '.global':
            symbol = self.object.symbol(rest.strip())
            if symbol.binding != elf.STB_WEAK:
                symbol.binding = elf.STB_GLOBAL
        elif name == '.weak':
            self.object.symbol(rest.strip()).binding = elf.STB_WEAK
        elif name == '.extern':
            # gas ignores `.extern`: an undefined symbol is external already,
            # and one never referenced stays out of the symbol table.
            pass
        elif name == '.hidden':
            self.object.symbol(rest.strip()).visibility = elf.STV_HIDDEN
        elif name in ('.quad', '.long', '.value'):
            size = {'.quad': 8, '.long': 4, '.value': 2}[name]
            for item in _split_operands(rest):
                self.value(section, item.strip(), size)
        elif name == '.byte':
            section.data.extend(_integer(item) & 0xFF for item in _split_operands(rest))
        elif name == '.uleb128':
            for item in _split_operands(rest):
                section.data.extend(_uleb128(_integer(item.strip())))
        elif name == '.string':
            section.data.extend(_string(rest) + b'\0')
        elif name == '.file':
            number, _, path = rest.partition(' ')
            self.files[_integer(number)] = _string(path).decode()
        elif name == '.loc':
            fields = rest.split()
            if self.loc is not None:
                # Two `.loc`s in a row: the first describes an empty range.
                self.row()
            self.loc = (_integer(fields[0]), _integer(fields[1]), _integer(fields[2]) if len(fields) > 2 else 0)
        elif name == '.zero':
            count = _integer(rest)
            if section.kind == elf.SHT_NOBITS:
                section.size += count
            else:
                section.data.extend(bytes(count))
        elif name == '.balign':
            alignment = _integer(rest.split(',')[0])
            section.align = max(section.align, alignment)
            padding = (-section.length()) % alignment
            if section.kind == elf.SHT_NOBITS:
                section.size += padding
            elif section.flags & elf.SHF_EXECINSTR:
                section.data.extend(_nops(padding))
            else:
                section.data.extend(bytes(padding))
        else:
            raise AssemblyError(f'unsupported directive {name}')

    def value(self, section: elf.Section, item: str, size: int) -> None:
        """A `.quad`/`.long`/`.value` item: a number, `label`, `label+n`, or
        `label - label` (resolved once both are placed)."""
        if item.lstrip('-')[:1].isdigit():
            section.data.extend((_integer(item) & ((1 << (8 * size)) - 1)).to_bytes(size, 'little'))
            return
        if ' - ' in item:
            left, _, right = item.partition(' - ')
            self.object.symbol(left.strip())
            self.object.symbol(right.strip())
            self.differences.append((self.current, len(section.data), size, left.strip(), right.strip()))
            section.data.extend(bytes(size))
            return
        if size == 2:
            raise AssemblyError('a 16-bit relocation')
        symbol, offset = _symbol_offset(item)
        self.object.symbol(symbol)
        section.relocations.append(elf.Relocation(len(section.data), R_X86_64_64 if size == 8 else R_X86_64_32,
                                                  symbol, offset))
        section.data.extend(bytes(size))

    def row(self) -> None:
        """The waiting `.loc` row, at the current offset."""
        file, line, column = self.loc
        self.loc = None
        self.rows.setdefault(self.current, []).append((len(self.data), file, line, column))

    # -- instructions ---------------------------------------------------
    def instruction(self, mnemonic: str, operands: list) -> None:
        count = len(operands)
        if mnemonic in ('ret', 'syscall', 'cqto', 'int3') and count == 0:
            self.emit(*{'ret': (0xC3,), 'syscall': (0x0F, 0x05), 'cqto': (0x48, 0x99), 'int3': (0xCC,)}[mnemonic])
            return
        if mnemonic in ('pushq', 'popq') and count == 1 and isinstance(operands[0], Register):
            register = operands[0].index
            if register & 8:
                self.emit(0x41)
            self.emit((0x50 if mnemonic == 'pushq' else 0x58) + (register & 7))
            return
        if mnemonic in ('call', 'jmp'):
            target = operands[0]
            if isinstance(target, Register):
                if target.index & 8:
                    self.emit(0x41)
                self.emit(0xFF, (0xD0 if mnemonic == 'call' else 0xE0) | (target.index & 7))
                return
            self.emit(0xE8 if mnemonic == 'call' else 0xE9)
            self.reference(target, -4, R_X86_64_PLT32)
            return
        if mnemonic.startswith('j') and mnemonic[1:] in CONDITIONS:
            self.emit(0x0F, 0x80 | CONDITIONS[mnemonic[1:]])
            self.reference(operands[0], -4, R_X86_64_PC32)
            return
        if mnemonic.startswith('set') and mnemonic[3:] in CONDITIONS and count == 1:
            register = operands[0]
            self.rex(False, 0, register.index, (register,))
            self.emit(0x0F, 0x90 | CONDITIONS[mnemonic[3:]])
            self.modrm(0, register)
            return
        if mnemonic in SSE and count == 2 and any(isinstance(o, Register) and o.width == 128 for o in operands):
            self.sse(mnemonic, *operands)
            return
        if mnemonic == 'movabsq':
            source, destination = operands
            self.rex(True, 0, destination.index)
            self.emit(0xB8 + (destination.index & 7))
            self.data.extend((source.value & (2**64 - 1)).to_bytes(8, 'little'))
            return
        suffix = mnemonic[-1]
        stem = mnemonic[:-1]
        if mnemonic in EXTENDS or mnemonic == 'movslq':
            source, destination = operands
            self.rex(True, destination.index, _rm_index(source), (source,) if isinstance(source, Register) else ())
            if mnemonic == 'movslq':
                self.emit(0x63)
            else:
                self.emit(*EXTENDS[mnemonic])
            self.modrm(destination.index, source)
            return
        if stem == 'mov':
            self.move(suffix, operands)
            return
        if stem == 'lea' and suffix == 'q':
            source, destination = operands
            self.rex(True, destination.index, _rm_index(source))
            self.emit(0x8D)
            self.modrm(destination.index, source)
            return
        if stem in ALU and suffix == 'q':
            self.alu(stem, operands)
            return
        if stem == 'test' and suffix == 'q':
            source, destination = operands
            self.rex(True, source.index, _rm_index(destination))
            self.emit(0x85)
            self.modrm(source.index, destination)
            return
        if stem == 'imul' and suffix == 'q':
            if count == 2 and isinstance(operands[0], Immediate):
                value, destination = operands[0].value, operands[1]
                self.rex(True, destination.index, destination.index)
                if _fits8(value):
                    self.emit(0x6B)
                    self.modrm(destination.index, destination)
                    self.emit(value & 0xFF)
                else:
                    self.emit(0x69)
                    self.modrm(destination.index, destination)
                    self.emit32(value)
                return
            source, destination = operands
            self.rex(True, destination.index, _rm_index(source))
            self.emit(0x0F, 0xAF)
            self.modrm(destination.index, source)
            return
        if stem in UNARY and suffix == 'q' and count == 1:
            operand = operands[0]
            self.rex(True, 0, _rm_index(operand))
            self.emit(0xF7)
            self.modrm(UNARY[stem], operand)
            return
        if stem in SHIFTS and suffix == 'q':
            amount, destination = operands
            self.rex(True, 0, _rm_index(destination))
            if isinstance(amount, Register):
                if amount.width != 8 or amount.index != 1:
                    raise AssemblyError('a variable shift count must be %cl')
                self.emit(0xD3)
                self.modrm(SHIFTS[stem], destination)
            elif amount.value == 1:
                self.emit(0xD1)
                self.modrm(SHIFTS[stem], destination)
            else:
                self.emit(0xC1)
                self.modrm(SHIFTS[stem], destination, 1)
                self.emit(amount.value & 0xFF)
            return
        raise AssemblyError(f'unsupported instruction {mnemonic}')

    def sse(self, mnemonic: str, source: Register, destination: Register) -> None:
        prefix, opcode, xmm_is_reg = SSE[mnemonic]
        if mnemonic in ('movd', 'movq') and source.width == 128:
            # xmm to a general register: the store form.
            opcode, reg, rm, general = 0x7E, source, destination, destination
        elif xmm_is_reg:
            reg, rm, general = destination, source, source
        else:
            reg, rm, general = destination, source, destination
        if (reg.width == 128) == (rm.width == 128):
            raise AssemblyError(f'{mnemonic} wants one xmm and one general register')
        self.emit(prefix)
        self.rex(general.width == 64, reg.index, rm.index)
        self.emit(0x0F, opcode)
        self.modrm(reg.index, rm)

    def move(self, suffix: str, operands: list) -> None:
        source, destination = operands
        width = {'q': 64, 'l': 32, 'w': 16, 'b': 8}[suffix]
        wide = width == 64
        if width == 16:
            self.emit(0x66)
        if isinstance(source, Immediate):
            value = source.value
            if isinstance(destination, Register) and wide and not _fits32(value):
                self.rex(True, 0, destination.index)
                self.emit(0xB8 + (destination.index & 7))
                self.data.extend((value & (2**64 - 1)).to_bytes(8, 'little'))
                return
            if not wide:
                raise AssemblyError(f'unsupported immediate mov{suffix}')
            self.rex(True, 0, _rm_index(destination))
            self.emit(0xC7)
            self.modrm(0, destination, 4)
            self.emit32(value)
            return
        if isinstance(source, Register):
            byte_registers = (source,) + ((destination,) if isinstance(destination, Register) else ())
            self.rex(wide, source.index, _rm_index(destination), byte_registers if width == 8 else ())
            self.emit(0x88 if width == 8 else 0x89)
            self.modrm(source.index, destination)
            return
        # memory -> register
        self.rex(wide, destination.index, _rm_index(source), (destination,) if width == 8 else ())
        self.emit(0x8A if width == 8 else 0x8B)
        self.modrm(destination.index, source)

    def alu(self, stem: str, operands: list) -> None:
        store, load, digit = ALU[stem]
        source, destination = operands
        if isinstance(source, Immediate):
            value = source.value
            self.rex(True, 0, _rm_index(destination))
            if _fits8(value):
                self.emit(0x83)
                self.modrm(digit, destination, 1)
                self.emit(value & 0xFF)
            elif isinstance(destination, Register) and destination.index == 0:
                self.emit(0x05 | (digit << 3))
                self.emit32(value)
            else:
                self.emit(0x81)
                self.modrm(digit, destination, 4)
                self.emit32(value)
            return
        if isinstance(source, Register):
            self.rex(True, source.index, _rm_index(destination))
            self.emit(store)
            self.modrm(source.index, destination)
            return
        self.rex(True, destination.index, _rm_index(source))
        self.emit(load)
        self.modrm(destination.index, source)

    # -- driver ---------------------------------------------------------
    def assemble(self, text: str) -> bytes:
        for line_number, raw in enumerate(text.split('\n'), 1):
            for statement in _statements(raw) if ('#' in raw or ';' in raw or '"' in raw) else (raw,):
                line = statement.strip()
                if not line:
                    continue
                try:
                    self.statement(line)
                except (AssemblyError, ValueError, KeyError, AttributeError, IndexError) as error:
                    raise AssemblyError(f'line {line_number}: {raw.strip()}: {error}') from None
        self.resolve()
        self.line_program()
        return self.object.write()

    def statement(self, line: str) -> None:
        if line.endswith(':') and ' ' not in line:
            self.label(line[:-1])
            return
        head, _, rest = line.partition(' ')
        if head.startswith('.'):
            self.directive(head, rest.strip())
            return
        if self.loc is not None:
            self.row()
        if head in ('call', 'jmp') or (head.startswith('j') and head[1:] in CONDITIONS):
            # A branch names a label, or `*%reg` for an indirect call.
            target = rest.strip()
            self.instruction(head, [_operand(target[1:]) if target.startswith('*%') else target])
            return
        self.instruction(head, [_operand(part) for part in _split_operands(rest)])

    def resolve(self) -> None:
        """Patch rel32 fields whose label lies in the same section; the rest become relocations."""
        for section_index, offset, symbol_name, addend, kind in self.pending:
            section = self.object.sections[section_index]
            symbol = self.object.symbols.get(symbol_name)
            # A label in the same section resolves now unless it is global
            # (a global symbol may be interposed; gas keeps its relocation).
            if symbol is not None and symbol.section == section_index and symbol.binding == elf.STB_LOCAL:
                section.data[offset:offset + 4] = struct.pack('<i', symbol.value + addend - offset)
                continue
            section.relocations.append(elf.Relocation(offset, kind, symbol_name, addend))
        for section_index, offset, size, left_name, right_name in self.differences:
            left, right = self.object.symbols[left_name], self.object.symbols[right_name]
            if left.section is None or left.section != right.section:
                raise AssemblyError(f'{left_name} - {right_name}: not two labels of one section')
            value = (left.value - right.value) & ((1 << (8 * size)) - 1)
            self.object.sections[section_index].data[offset:offset + size] = value.to_bytes(size, 'little')

    def line_program(self) -> None:
        """`.debug_line` from the `.loc` rows, as gas writes it: a DWARF 3
        header naming the `.file`s (directory and base name apart), then one
        sequence per section with rows."""
        if not self.rows:
            return
        directories: list[str] = []
        files = bytearray()
        for number in range(1, max(self.files, default=0) + 1):
            path = self.files.get(number, '')
            directory, slash, base = path.rpartition('/')
            index = 0
            if slash:
                directory = directory or '/'
                if directory not in directories:
                    directories.append(directory)
                index = directories.index(directory) + 1
            files += base.encode() + b'\0' + _uleb128(index) + b'\0\0'
        header = bytes([1, 1, LINE_BASE & 0xFF, LINE_RANGE, OPCODE_BASE]) + STANDARD_OPCODE_LENGTHS
        header += b''.join(directory.encode() + b'\0' for directory in directories) + b'\0' + files + b'\0'
        index = self.object.section('.debug_line')
        section = self.object.sections[index]
        start = len(section.data)
        program = bytearray()
        # The program's offset in the section, for its address relocations.
        base = start + 4 + 2 + 4 + len(header)
        for section_index, rows in self.rows.items():
            address, file, line, column = 0, 1, 1, 0
            for position, (offset, row_file, row_line, row_column) in enumerate(rows):
                if row_file != file:
                    program += bytes([DW_LNS_set_file]) + _uleb128(row_file)
                    file = row_file
                if row_column != column:
                    program += bytes([DW_LNS_set_column]) + _uleb128(row_column)
                    column = row_column
                if position == 0:
                    # DW_LNE_set_address to the row, through a temporary label
                    # (a reference through the section symbol).
                    label = self.object.symbol(f'.Lline{section_index}')
                    label.section, label.value = section_index, offset
                    program += bytes([0, 9, DW_LNE_set_address])
                    section.relocations.append(elf.Relocation(base + len(program), R_X86_64_64, label.name, 0))
                    program += bytes(8)
                    address = offset
                self.advance(program, row_line - line, offset - address)
                line, address = row_line, offset
            end = self.object.sections[section_index].length()
            if end > address:
                program += bytes([DW_LNS_advance_pc]) + _uleb128(end - address)
            program += bytes([0, 1, DW_LNE_end_sequence])
        header_length = len(header)
        unit = struct.pack('<HI', LINE_VERSION, header_length) + header + program
        section.data += struct.pack('<I', len(unit)) + unit

    @staticmethod
    def advance(program: bytearray, line_delta: int, address_delta: int) -> None:
        """A row `line_delta` lines and `address_delta` bytes on: one special
        opcode when it fits, else advance_line / advance_pc and copy."""
        if LINE_BASE <= line_delta < LINE_BASE + LINE_RANGE:
            opcode = (line_delta - LINE_BASE) + LINE_RANGE * address_delta + OPCODE_BASE
            if opcode <= 255:
                program.append(opcode)
                return
        if line_delta:
            program += bytes([DW_LNS_advance_line]) + _sleb128(line_delta)
        if address_delta:
            program += bytes([DW_LNS_advance_pc]) + _uleb128(address_delta)
        program.append(DW_LNS_copy)


def _rm_index(operand) -> int:
    if isinstance(operand, Register):
        return operand.index
    return 0 if operand.base is None else operand.base


def _nops(count: int) -> bytes:
    """Padding for executable sections: single-byte NOPs."""
    return b'\x90' * count


def assemble(text: str) -> bytes:
    """The ELF object for x86-64 assembly `text` from the µDewy backend."""
    return Assembler().assemble(text)


if __name__ == '__main__':
    # `python -m udewy.backend.x86_64_object in.s out.o`: the direct path on
    # its own, for comparing it with `as` (tools/compare_objects.py).
    import sys
    if len(sys.argv) != 3:
        sys.exit('usage: python -m udewy.backend.x86_64_object in.s out.o')
    with open(sys.argv[1]) as source, open(sys.argv[2], 'wb') as output:
        output.write(assemble(source.read()))
