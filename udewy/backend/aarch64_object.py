"""AArch64 assembly text to an ELF relocatable object, without an assembler.

The arm backend emits a closed set of AArch64 instructions and directives
(see ROADMAP "Direct binary fast path"). Instructions are fixed 32-bit words;
this encodes exactly that set, including the aliases an assembler resolves
(`mov` as `orr`, `add #0`, `movz`, `movn` or a bitmask `orr`; `csetm` as
`csinv`; `cmp` as `subs`) and `ldr xN, =imm` as a load from a literal pool
at the end of its section, as assemblers place it. Local branches resolve at
the end; `bl`/`b` to a symbol, `adrp` and `:lo12:` operands, and `.xword sym`
become relocations. Anything else is an error, never a guess. Mirrors
`udewy/bootstrap/backend/aarch64_object.udewy`.
"""
from __future__ import annotations

import struct

from . import elf

R_AARCH64_ABS64 = 257
R_AARCH64_ADR_PREL_PG_HI21 = 275
R_AARCH64_ADD_ABS_LO12_NC = 277
R_AARCH64_JUMP26 = 282
R_AARCH64_CALL26 = 283
R_AARCH64_LDST64_ABS_LO12_NC = 286

CONDITIONS = {'eq': 0, 'ne': 1, 'cs': 2, 'hs': 2, 'cc': 3, 'lo': 3, 'mi': 4, 'pl': 5, 'vs': 6, 'vc': 7,
              'hi': 8, 'ls': 9, 'ge': 10, 'lt': 11, 'gt': 12, 'le': 13, 'al': 14}


class AssemblyError(Exception):
    pass


class Register:
    __slots__ = ('number', 'wide', 'sp', 'fp')

    def __init__(self, number: int, wide: bool, sp: bool = False, fp: str | None = None):
        self.number = number
        self.wide = wide
        self.sp = sp          # `sp`/`wsp`: register 31 where the encoding means SP
        self.fp = fp          # 'd' or 's' for floating-point registers


class Immediate:
    __slots__ = ('value', 'shift')

    def __init__(self, value: int, shift: int = 0):
        self.value = value
        self.shift = shift


class Memory:
    """`[base]`, `[base, #imm]`, `[base, #imm]!` (pre-index) or `[base], #imm` (post-index)."""
    __slots__ = ('base', 'offset', 'mode')

    def __init__(self, base: Register, offset: int, mode: str):
        self.base = base
        self.offset = offset
        self.mode = mode      # 'offset', 'pre' or 'post'


class Symbol:
    __slots__ = ('name', 'addend', 'lo12')

    def __init__(self, name: str, addend: int = 0, lo12: bool = False):
        self.name = name
        self.addend = addend
        self.lo12 = lo12


class Literal:
    __slots__ = ('value',)

    def __init__(self, value: int):
        self.value = value


def _integer(text: str) -> int:
    return int(text.replace('_', ''), 0)


def _register(text: str) -> Register | None:
    text = text.strip().lower()
    if text in ('sp', 'wsp'):
        return Register(31, text == 'sp', sp=True)
    if text in ('xzr', 'wzr'):
        return Register(31, text == 'xzr')
    if len(text) >= 2 and text[0] in 'xwds' and text[1:].isdigit():
        number = int(text[1:])
        if text[0] in 'xw' and number <= 30:
            return Register(number, text[0] == 'x')
        if text[0] in 'ds' and number <= 31:
            return Register(number, text[0] == 'd', fp=text[0])
    return None


def _symbol(text: str) -> Symbol:
    lo12 = text.startswith(':lo12:')
    if lo12:
        text = text[len(':lo12:'):]
    for sign in ('+', '-'):
        at = text.rfind(sign, 1)
        if at > 0 and text[at + 1:at + 2].isdigit():
            value = _integer(text[at + 1:])
            return Symbol(text[:at], value if sign == '+' else -value, lo12)
    return Symbol(text, 0, lo12)


def _split(text: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    start = 0
    for at, char in enumerate(text):
        if char == '[':
            depth += 1
        elif char == ']':
            depth -= 1
        elif char == ',' and depth == 0:
            parts.append(text[start:at].strip())
            start = at + 1
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def _operands(text: str) -> list:
    parts = _split(text)
    operands: list = []
    index = 0
    while index < len(parts):
        part = parts[index]
        if part.startswith('['):
            pre = part.endswith('!')
            inner = part[1:part.rindex(']')]
            fields = [field.strip() for field in inner.split(',')]
            base = _register(fields[0])
            if base is None:
                raise AssemblyError(f'unsupported memory base {fields[0]}')
            offset = _integer(fields[1].lstrip('#')) if len(fields) > 1 else 0
            mode = 'pre' if pre else 'offset'
            # `[base], #imm`: post-index takes the next operand.
            if not pre and len(fields) == 1 and index + 1 < len(parts) and parts[index + 1].startswith('#'):
                offset = _integer(parts[index + 1][1:])
                mode = 'post'
                index += 1
            operands.append(Memory(base, offset, mode))
        elif part.startswith('#'):
            body = part[1:]
            operands.append(Immediate(_integer(body)))
        elif part.startswith('='):
            operands.append(Literal(_integer(part[1:])))
        elif part.startswith('lsl') and operands and isinstance(operands[-1], Immediate):
            operands[-1].shift = _integer(part.split('#', 1)[1])
        else:
            register = _register(part)
            if register is not None:
                operands.append(register)
            elif part.lower() in CONDITIONS:
                operands.append(part.lower())
            else:
                operands.append(_symbol(part))
        index += 1
    return operands


def _bitmask(value: int, wide: bool) -> int | None:
    """The N:immr:imms encoding of a logical immediate, or None."""
    size = 64 if wide else 32
    value &= (1 << size) - 1
    if value in (0, (1 << size) - 1):
        return None
    element = size
    while element > 2:
        half = element // 2
        mask = (1 << half) - 1
        if (value & mask) != ((value >> half) & mask):
            break
        element = half
    mask = (1 << element) - 1
    pattern = value & mask
    ones = bin(pattern).count('1')
    # The run of ones, rotated right by `rotation` into the low bits.
    for rotation in range(element):
        rotated = ((pattern >> rotation) | (pattern << (element - rotation))) & mask
        if rotated == (1 << ones) - 1:
            immr = (element - rotation) % element
            break
    else:
        return None
    imms = ((~(element - 1) << 1) & 0x3F) | (ones - 1)
    n = 1 if element == 64 else 0
    return (n << 12) | (immr << 6) | imms


class Assembler:
    def __init__(self):
        self.object = elf.ObjectFile(elf.EM_AARCH64)
        self.current = self.object.section('.text', elf.SHT_PROGBITS, elf.SHF_ALLOC | elf.SHF_EXECINSTR)
        self.object.section('.data', elf.SHT_PROGBITS, elf.SHF_ALLOC | elf.SHF_WRITE)
        self.object.section('.bss', elf.SHT_NOBITS, elf.SHF_ALLOC | elf.SHF_WRITE)
        # Branches to labels resolved at the end: (section, offset, symbol, kind).
        self.pending: list[tuple[int, int, str, str]] = []
        # Literal pool loads per section: (offset of the ldr, value).
        self.literals: dict[int, list[tuple[int, int]]] = {}

    @property
    def data(self) -> bytearray:
        return self.object.sections[self.current].data

    def word(self, value: int) -> None:
        self.data.extend(struct.pack('<I', value & 0xFFFFFFFF))

    def relocation(self, kind: int, symbol: str, addend: int) -> None:
        self.object.symbol(symbol)
        section = self.object.sections[self.current]
        section.relocations.append(elf.Relocation(len(section.data), kind, symbol, addend))

    # -- directives ---------------------------------------------------------
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
            flags = 0
            for letter in (parts[1].strip('"') if len(parts) > 1 else ''):
                flags |= elf.FLAG_LETTERS[letter]
            kind = elf.SHT_NOBITS if len(parts) > 2 and parts[2] == '@nobits' else elf.SHT_PROGBITS
            self.current = self.object.section(parts[0], kind, flags)
        elif name in ('.globl', '.global'):
            symbol = self.object.symbol(rest.strip())
            if symbol.binding != elf.STB_WEAK:
                symbol.binding = elf.STB_GLOBAL
        elif name == '.weak':
            self.object.symbol(rest.strip()).binding = elf.STB_WEAK
        elif name == '.hidden':
            self.object.symbol(rest.strip()).visibility = elf.STV_HIDDEN
        elif name == '.extern':
            pass
        elif name in ('.xword', '.quad', '.dword'):
            for item in _split(rest):
                if item.lstrip('-')[:1].isdigit():
                    section.data.extend((_integer(item) & (2**64 - 1)).to_bytes(8, 'little'))
                else:
                    symbol = _symbol(item)
                    self.relocation(R_AARCH64_ABS64, symbol.name, symbol.addend)
                    section.data.extend(bytes(8))
        elif name in ('.word', '.long'):
            for item in _split(rest):
                section.data.extend((_integer(item) & 0xFFFFFFFF).to_bytes(4, 'little'))
        elif name == '.byte':
            section.data.extend(_integer(item) & 0xFF for item in _split(rest))
        elif name == '.zero':
            count = _integer(rest)
            if section.kind == elf.SHT_NOBITS:
                section.size += count
            else:
                section.data.extend(bytes(count))
        elif name in ('.balign', '.p2align', '.align'):
            alignment = _integer(rest.split(',')[0])
            if name != '.balign':
                alignment = 1 << alignment
            section.align = max(section.align, alignment)
            padding = (-section.length()) % alignment
            if section.kind == elf.SHT_NOBITS:
                section.size += padding
            elif section.flags & elf.SHF_EXECINSTR:
                self._pad_nops(padding)
            else:
                section.data.extend(bytes(padding))
        else:
            raise AssemblyError(f'unsupported directive {name}')

    def _pad_nops(self, padding: int) -> None:
        if padding % 4:
            raise AssemblyError('unaligned code')
        for _ in range(padding // 4):
            self.word(0xD503201F)

    def label(self, name: str) -> None:
        symbol = self.object.symbol(name)
        if symbol.section is not None:
            raise AssemblyError(f'label {name} defined twice')
        symbol.section = self.current
        symbol.value = self.object.sections[self.current].length()

    # -- instructions -------------------------------------------------------
    def instruction(self, mnemonic: str, operands: list) -> None:
        m = mnemonic.lower()
        if m == 'ret':
            self.word(0xD65F03C0 | ((operands[0].number if operands else 30) << 5))
            return
        if m == 'nop':
            self.word(0xD503201F)
            return
        if m == 'svc':
            self.word(0xD4000001 | ((operands[0].value & 0xFFFF) << 5))
            return
        if m == 'brk':
            self.word(0xD4200000 | ((operands[0].value & 0xFFFF) << 5))
            return
        if m in ('b', 'bl'):
            self.branch(0x94000000 if m == 'bl' else 0x14000000, operands[0], 'call26' if m == 'bl' else 'jump26')
            return
        if m.startswith('b.') or (m[:1] == 'b' and m[1:] in CONDITIONS and m not in ('bl',)):
            condition = CONDITIONS[m[2:] if m.startswith('b.') else m[1:]]
            self.branch(0x54000000 | condition, operands[0], 'cond19')
            return
        if m in ('cbz', 'cbnz'):
            register = operands[0]
            base = (0xB4000000 if register.wide else 0x34000000) | (0x01000000 if m == 'cbnz' else 0)
            self.branch(base | register.number, operands[1], 'cond19')
            return
        if m in ('blr', 'br'):
            self.word((0xD63F0000 if m == 'blr' else 0xD61F0000) | (operands[0].number << 5))
            return
        if m == 'adrp':
            destination, symbol = operands
            self.relocation(R_AARCH64_ADR_PREL_PG_HI21, symbol.name, symbol.addend)
            self.word(0x90000000 | destination.number)
            return
        if m == 'mov':
            self.move(operands)
            return
        if m in ('add', 'sub', 'adds', 'subs'):
            self.add_sub(m, operands)
            return
        if m == 'cmp':
            self.add_sub('subs', [Register(31, operands[0].wide)] + operands)
            return
        if m == 'cmn':
            self.add_sub('adds', [Register(31, operands[0].wide)] + operands)
            return
        if m == 'neg':
            destination, source = operands
            self.word((0xCB0003E0 if destination.wide else 0x4B0003E0) | (source.number << 16) | destination.number)
            return
        if m == 'mvn':
            destination, source = operands
            self.word((0xAA2003E0 if destination.wide else 0x2A2003E0) | (source.number << 16) | destination.number)
            return
        if m in ('and', 'orr', 'eor', 'ands', 'bic', 'orn', 'eon', 'bics'):
            self.logical(m, operands)
            return
        if m in ('mul', 'madd', 'msub'):
            destination, left, right = operands[:3]
            accumulate = operands[3].number if len(operands) > 3 else 31
            base = 0x9B000000 if destination.wide else 0x1B000000
            if m == 'msub':
                base |= 0x8000
            self.word(base | (right.number << 16) | (accumulate << 10) | (left.number << 5) | destination.number)
            return
        if m in ('sdiv', 'udiv', 'lslv', 'lsrv', 'asrv', 'lsl', 'lsr', 'asr') and isinstance(operands[2], Register):
            op = {'sdiv': 0x0C00, 'udiv': 0x0800, 'lslv': 0x2000, 'lsl': 0x2000, 'lsrv': 0x2400, 'lsr': 0x2400,
                  'asrv': 0x2800, 'asr': 0x2800}[m]
            destination, left, right = operands
            base = 0x9AC00000 if destination.wide else 0x1AC00000
            self.word(base | op | (right.number << 16) | (left.number << 5) | destination.number)
            return
        if m in ('lsl', 'lsr', 'asr'):
            destination, source, amount = operands
            size = 64 if destination.wide else 32
            shift = amount.value % size
            if m == 'lsl':
                self.bitfield(0xD3400000 if destination.wide else 0x53000000, destination, source,
                              (size - shift) % size, size - 1 - shift)
            else:
                self.bitfield((0xD3400000 if m == 'lsr' else 0x93400000) if destination.wide else
                              (0x53000000 if m == 'lsr' else 0x13000000), destination, source, shift, size - 1)
            return
        if m == 'csetm':
            destination, condition = operands
            inverted = CONDITIONS[condition] ^ 1
            base = 0xDA800000 if destination.wide else 0x5A800000
            self.word(base | (31 << 16) | (inverted << 12) | (31 << 5) | destination.number)
            return
        if m == 'cset':
            destination, condition = operands
            inverted = CONDITIONS[condition] ^ 1
            base = 0x9A800400 if destination.wide else 0x1A800400
            self.word(base | (31 << 16) | (inverted << 12) | (31 << 5) | destination.number)
            return
        if m in ('ldp', 'stp'):
            self.pair(m, operands)
            return
        if m in ('ldr', 'str', 'ldrb', 'strb', 'ldrh', 'strh', 'ldrsb', 'ldrsh', 'ldrsw', 'ldur', 'stur'):
            self.load_store(m, operands)
            return
        if m == 'fmov':
            destination, source = operands
            if destination.fp and not source.fp:
                self.word((0x9E670000 if destination.fp == 'd' else 0x1E270000) | (source.number << 5) | destination.number)
            elif source.fp and not destination.fp:
                self.word((0x9E660000 if source.fp == 'd' else 0x1E260000) | (source.number << 5) | destination.number)
            else:
                raise AssemblyError('unsupported fmov')
            return
        if m == 'scvtf':
            destination, source = operands
            base = 0x9E620000 if destination.fp == 'd' else 0x9E220000
            if not source.wide:
                base &= 0x7FFFFFFF
            self.word(base | (source.number << 5) | destination.number)
            return
        if m == 'fcvtzs':
            destination, source = operands
            base = 0x9E780000 if source.fp == 'd' else 0x9E380000
            if not destination.wide:
                base &= 0x7FFFFFFF
            self.word(base | (source.number << 5) | destination.number)
            return
        raise AssemblyError(f'unsupported instruction {mnemonic}')

    def bitfield(self, base: int, destination, source, immr: int, imms: int) -> None:
        self.word(base | (immr << 16) | (imms << 10) | (source.number << 5) | destination.number)

    def branch(self, base: int, target, kind: str) -> None:
        section = self.object.sections[self.current]
        self.pending.append((self.current, len(section.data), target.name, kind))
        self.object.symbol(target.name)
        self.word(base)

    def move(self, operands: list) -> None:
        destination, source = operands
        if isinstance(source, Register):
            if destination.sp or source.sp:
                # `mov` to or from SP is `add xd, xn, #0`.
                self.word((0x91000000 if destination.wide else 0x11000000) | (source.number << 5) | destination.number)
            else:
                # `mov xd, xm` is `orr xd, xzr, xm`.
                self.word((0xAA0003E0 if destination.wide else 0x2A0003E0) | (source.number << 16) | destination.number)
            return
        if isinstance(source, Literal):
            self.load_literal(destination, source.value)
            return
        if self.wide_move(destination, source.value):
            return
        size = 64 if destination.wide else 32
        value = source.value & ((1 << size) - 1)
        encoded = _bitmask(value, destination.wide)
        if encoded is None:
            raise AssemblyError(f'immediate {source.value} does not fit a mov')
        base = 0xB2000000 if destination.wide else 0x32000000
        self.word(base | (encoded << 10) | (31 << 5) | destination.number)

    def wide_move(self, destination: Register, value: int, allow_movn: bool = True) -> bool:
        """A single movz (or movn) for `value`, if one builds it."""
        size = 64 if destination.wide else 32
        value &= (1 << size) - 1
        movz = 0xD2800000 if destination.wide else 0x52800000
        movn = 0x92800000 if destination.wide else 0x12800000
        for chunk in range(size // 16):
            if value & ~(0xFFFF << (16 * chunk)) & ((1 << size) - 1) == 0:
                self.word(movz | (chunk << 21) | (((value >> (16 * chunk)) & 0xFFFF) << 5) | destination.number)
                return True
        if not allow_movn:
            return False
        inverted = ~value & ((1 << size) - 1)
        for chunk in range(size // 16):
            if inverted & ~(0xFFFF << (16 * chunk)) & ((1 << size) - 1) == 0:
                self.word(movn | (chunk << 21) | (((inverted >> (16 * chunk)) & 0xFFFF) << 5) | destination.number)
                return True
        return False

    def load_literal(self, destination: Register, value: int) -> None:
        # Like an assembler, a constant one movz builds needs no literal
        # pool entry (a movn-shaped one still goes to the pool).
        if self.wide_move(destination, value, allow_movn=False):
            return
        section = self.object.sections[self.current]
        self.literals.setdefault(self.current, []).append((len(section.data), value, destination.wide))
        self.word((0x58000000 if destination.wide else 0x18000000) | destination.number)

    def add_sub(self, m: str, operands: list) -> None:
        destination, left, right = operands[:3]
        wide = destination.wide
        subtract = m.startswith('sub')
        flags = m.endswith('s')
        if isinstance(right, Symbol):
            if not right.lo12:
                raise AssemblyError('an add of a symbol needs :lo12:')
            self.relocation(R_AARCH64_ADD_ABS_LO12_NC, right.name, right.addend)
            self.word((0x91000000 if wide else 0x11000000) | (left.number << 5) | destination.number)
            return
        if isinstance(right, Immediate):
            value = right.value
            shift = 1 if right.shift == 12 else 0
            if value < 0:
                value = -value
                subtract = not subtract
            if value > 0xFFF:
                if value & 0xFFF or value >> 12 > 0xFFF:
                    raise AssemblyError('immediate does not fit add/sub')
                value >>= 12
                shift = 1
            base = 0x11000000 | (0x40000000 if subtract else 0) | (0x20000000 if flags else 0) | (0x80000000 if wide else 0)
            self.word(base | (shift << 22) | (value << 10) | (left.number << 5) | destination.number)
            return
        base = (0x0B000000 | (0x40000000 if subtract else 0) | (0x20000000 if flags else 0) |
                (0x80000000 if wide else 0))
        if left.sp or destination.sp:
            # SP operands need the extended-register form (UXTX / UXTW).
            option = 3 if wide else 2
            self.word(base | 0x00200000 | (right.number << 16) | (option << 13) | (left.number << 5) | destination.number)
            return
        self.word(base | (right.number << 16) | (left.number << 5) | destination.number)

    def logical(self, m: str, operands: list) -> None:
        destination, left, right = operands[:3]
        wide = destination.wide
        opc = {'and': 0, 'bic': 0, 'orr': 1, 'orn': 1, 'eor': 2, 'eon': 2, 'ands': 3, 'bics': 3}[m]
        negate = m in ('bic', 'orn', 'eon', 'bics')
        if isinstance(right, Immediate):
            value = ~right.value if negate else right.value
            encoded = _bitmask(value, wide)
            if encoded is None:
                raise AssemblyError(f'#{right.value} is not a logical immediate')
            base = 0x12000000 | (opc << 29) | (0x80000000 if wide else 0)
            self.word(base | (encoded << 10) | (left.number << 5) | destination.number)
            return
        base = 0x0A000000 | (opc << 29) | (0x80000000 if wide else 0) | (0x00200000 if negate else 0)
        self.word(base | (right.number << 16) | (left.number << 5) | destination.number)

    def pair(self, m: str, operands: list) -> None:
        first, second, memory = operands
        scale = 3 if first.wide else 2
        offset = memory.offset >> scale
        if memory.offset & ((1 << scale) - 1) or not -64 <= offset <= 63:
            raise AssemblyError('pair offset out of range')
        mode = {'post': 0x1, 'offset': 0x2, 'pre': 0x3}[memory.mode]
        base = (0xA8000000 if first.wide else 0x28000000) | (mode << 23) | (0x00400000 if m == 'ldp' else 0)
        self.word(base | ((offset & 0x7F) << 15) | (second.number << 10) | (memory.base.number << 5) | first.number)

    def load_store(self, m: str, operands: list) -> None:
        register, address = operands[0], operands[1]
        if isinstance(address, Literal):
            self.load_literal(register, address.value)
            return
        if isinstance(address, Symbol):
            raise AssemblyError('pc-relative loads of symbols are not supported')
        # size (log2 bytes) and opc of the unsigned-offset/unscaled forms
        table = {
            'ldr': (3 if register.wide else 2, 1), 'str': (3 if register.wide else 2, 0),
            'ldrb': (0, 1), 'strb': (0, 0), 'ldrh': (1, 1), 'strh': (1, 0),
            'ldrsb': (0, 2 if register.wide else 3), 'ldrsh': (1, 2 if register.wide else 3), 'ldrsw': (2, 2),
            'ldur': (3 if register.wide else 2, 1), 'stur': (3 if register.wide else 2, 0),
        }
        size, opc = table[m]
        base_number = address.base.number
        offset = address.offset
        if len(operands) > 2 and isinstance(operands[2], Symbol) and operands[2].lo12:
            raise AssemblyError('unsupported :lo12: load form')
        if address.mode in ('pre', 'post'):
            if not -256 <= offset <= 255:
                raise AssemblyError('pre/post-index offset out of range')
            mode = 0x3 if address.mode == 'pre' else 0x1
            self.word((size << 30) | 0x38000000 | (opc << 22) | ((offset & 0x1FF) << 12) | (mode << 10) |
                      (base_number << 5) | register.number)
            return
        if m not in ('ldur', 'stur') and offset >= 0 and offset & ((1 << size) - 1) == 0 and offset >> size <= 0xFFF:
            self.word((size << 30) | 0x39000000 | (opc << 22) | ((offset >> size) << 10) | (base_number << 5) |
                      register.number)
            return
        if -256 <= offset <= 255:
            # An unscaled offset (ldur/stur), as an assembler picks for
            # negative or unaligned offsets.
            self.word((size << 30) | 0x38000000 | (opc << 22) | ((offset & 0x1FF) << 12) | (base_number << 5) |
                      register.number)
            return
        raise AssemblyError('load/store offset out of range')

    # -- driver -------------------------------------------------------------
    def assemble(self, text: str) -> bytes:
        for line_number, raw in enumerate(text.split('\n'), 1):
            line = raw.split('//', 1)[0].strip()
            if not line:
                continue
            try:
                if line.endswith(':') and ' ' not in line:
                    self.label(line[:-1])
                    continue
                head, _, rest = line.partition(' ')
                if head.startswith('.'):
                    self.directive(head, rest.strip())
                    continue
                # A section holding code is word-aligned, as assemblers make it.
                section = self.object.sections[self.current]
                section.align = max(section.align, 4)
                self.instruction(head, _operands(rest))
            except (AssemblyError, ValueError, KeyError, AttributeError, IndexError, TypeError) as error:
                raise AssemblyError(f'line {line_number}: {raw.strip()}: {error}') from None
        self.place_literals()
        self.resolve()
        return self.object.write()

    def place_literals(self) -> None:
        """Each section's literal pool at its end, as an assembler places it."""
        for section_index, loads in self.literals.items():
            section = self.object.sections[section_index]
            pool: dict[tuple[int, bool], int] = {}
            for offset, value, wide in loads:
                key = (value & ((1 << 64) - 1) if wide else value & 0xFFFFFFFF, wide)
                if key not in pool:
                    size = 8 if wide else 4
                    while len(section.data) % size:
                        section.data.extend(bytes(1))
                    pool[key] = len(section.data)
                    section.data.extend(key[0].to_bytes(size, 'little'))
                    section.align = max(section.align, size)
                delta = (pool[key] - offset) >> 2
                instruction, = struct.unpack_from('<I', section.data, offset)
                struct.pack_into('<I', section.data, offset, instruction | ((delta & 0x7FFFF) << 5))

    def resolve(self) -> None:
        for section_index, offset, name, kind in self.pending:
            section = self.object.sections[section_index]
            symbol = self.object.symbols.get(name)
            instruction, = struct.unpack_from('<I', section.data, offset)
            if symbol is not None and symbol.section == section_index and symbol.binding == elf.STB_LOCAL:
                delta = (symbol.value - offset) >> 2
                if kind == 'cond19':
                    instruction |= (delta & 0x7FFFF) << 5
                else:
                    instruction |= delta & 0x3FFFFFF
                struct.pack_into('<I', section.data, offset, instruction)
                continue
            if kind == 'cond19':
                raise AssemblyError(f'conditional branch to {name} outside its section')
            section.relocations.append(elf.Relocation(offset, R_AARCH64_CALL26 if kind == 'call26' else R_AARCH64_JUMP26,
                                                      name, 0))


def assemble(text: str) -> bytes:
    """The ELF object for AArch64 assembly `text` from the µDewy arm backend."""
    return Assembler().assemble(text)


if __name__ == '__main__':
    # `python -m udewy.backend.aarch64_object in.s out.o`: the direct path on
    # its own, for comparing it with an assembler.
    import sys
    if len(sys.argv) != 3:
        sys.exit('usage: python -m udewy.backend.aarch64_object in.s out.o')
    with open(sys.argv[1]) as source, open(sys.argv[2], 'wb') as output:
        output.write(assemble(source.read()))
