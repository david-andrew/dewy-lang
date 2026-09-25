"""RISC-V (RV64IMFD) assembly text to an ELF relocatable object, without an assembler.

The riscv backend emits a closed set of instructions, pseudo-instructions
and directives (see ROADMAP "Direct binary fast path"). This writes the long
form the roadmap chose: `li` expands as LLVM's RISCVMatInt does
(`riscv_materialize`), `la` is `auipc` + `addi` with `R_RISCV_PCREL_HI20` and
`R_RISCV_PCREL_LO12_I` (the low part naming the `auipc`'s `.Lpcrel_hiN`
label), and `call` is `auipc` + `jalr` with `R_RISCV_CALL_PLT`; no
instruction is compressed and nothing carries `R_RISCV_RELAX`, so the linker
never rewrites code (`_start` depends on that for `la gp`). A conditional
branch whose target is out of range becomes the inverted branch over a
`jal`, as `llvm-mc` relaxes it. Anything else is an error, never a guess.
Mirrors `udewy/bootstrap/backend/riscv_object.udewy`.
"""
from __future__ import annotations

import struct

from . import elf
from .riscv_materialize import materialize

R_RISCV_64 = 2
R_RISCV_BRANCH = 16
R_RISCV_JAL = 17
R_RISCV_CALL_PLT = 19
R_RISCV_PCREL_HI20 = 23
R_RISCV_PCREL_LO12_I = 24
EM_RISCV = 243
EF_RISCV_FLOAT_ABI_DOUBLE = 0x4

INTEGER_NAMES = ['zero', 'ra', 'sp', 'gp', 'tp', 't0', 't1', 't2', 's0', 's1', 'a0', 'a1', 'a2', 'a3', 'a4', 'a5',
                 'a6', 'a7', 's2', 's3', 's4', 's5', 's6', 's7', 's8', 's9', 's10', 's11', 't3', 't4', 't5', 't6']
FLOAT_NAMES = ['ft0', 'ft1', 'ft2', 'ft3', 'ft4', 'ft5', 'ft6', 'ft7', 'fs0', 'fs1', 'fa0', 'fa1', 'fa2', 'fa3', 'fa4',
               'fa5', 'fa6', 'fa7', 'fs2', 'fs3', 'fs4', 'fs5', 'fs6', 'fs7', 'fs8', 'fs9', 'fs10', 'fs11', 'ft8', 'ft9',
               'ft10', 'ft11']
REGISTERS = {name: index for index, name in enumerate(INTEGER_NAMES)}
REGISTERS.update({f'x{index}': index for index in range(32)})
REGISTERS['fp'] = 8
FLOATS = {name: index for index, name in enumerate(FLOAT_NAMES)}
FLOATS.update({f'f{index}': index for index in range(32)})

# funct7, funct3 of R-type integer operations (opcode 0x33).
R_TYPE = {'add': (0x00, 0), 'sub': (0x20, 0), 'sll': (0x00, 1), 'slt': (0x00, 2), 'sltu': (0x00, 3), 'xor': (0x00, 4),
          'srl': (0x00, 5), 'sra': (0x20, 5), 'or': (0x00, 6), 'and': (0x00, 7), 'mul': (0x01, 0), 'mulh': (0x01, 1),
          'div': (0x01, 4), 'divu': (0x01, 5), 'rem': (0x01, 6), 'remu': (0x01, 7)}
# funct3 of I-type arithmetic (opcode 0x13).
I_TYPE = {'addi': 0, 'slti': 2, 'sltiu': 3, 'xori': 4, 'ori': 6, 'andi': 7}
SHIFTS = {'slli': (0x00, 1), 'srli': (0x00, 5), 'srai': (0x10, 5)}
LOADS = {'lb': 0, 'lh': 1, 'lw': 2, 'ld': 3, 'lbu': 4, 'lhu': 5, 'lwu': 6}
STORES = {'sb': 0, 'sh': 1, 'sw': 2, 'sd': 3}
BRANCHES = {'beq': 0, 'bne': 1, 'blt': 4, 'bge': 5, 'bltu': 6, 'bgeu': 7}
# Branch pseudo-instructions: (real branch, swap operands, compare with zero on the right/left).
BRANCH_PSEUDOS = {'bgt': ('blt', True), 'ble': ('bge', True), 'bgtu': ('bltu', True), 'bleu': ('bgeu', True)}
ZERO_BRANCHES = {'beqz': ('beq', False), 'bnez': ('bne', False), 'bltz': ('blt', False), 'bgez': ('bge', False),
                 'blez': ('bge', True), 'bgtz': ('blt', True)}
# Floating-point moves and conversions: funct7, rs2 field, funct3.
FLOAT_OPS = {'fmv.x.w': (0x70, 0, 0), 'fmv.w.x': (0x78, 0, 0), 'fmv.x.d': (0x71, 0, 0), 'fmv.d.x': (0x79, 0, 0),
             'fcvt.s.l': (0x68, 2, 7), 'fcvt.d.l': (0x69, 2, 7), 'fcvt.l.s': (0x60, 2, 7), 'fcvt.l.d': (0x61, 2, 7)}


class AssemblyError(Exception):
    pass


def _integer(text: str) -> int:
    return int(text.replace('_', ''), 0)


def _register(text: str) -> int:
    text = text.strip()
    if text not in REGISTERS:
        raise AssemblyError(f'unknown register {text}')
    return REGISTERS[text]


def _float(text: str) -> int:
    text = text.strip()
    if text not in FLOATS:
        raise AssemblyError(f'unknown floating-point register {text}')
    return FLOATS[text]


def _memory(text: str) -> tuple[int, int]:
    """`offset(base)` -> (offset, base)."""
    open_at = text.index('(')
    offset = _integer(text[:open_at]) if text[:open_at].strip() else 0
    return offset, _register(text[open_at + 1:text.rindex(')')])


def _symbol(text: str) -> tuple[str, int]:
    for sign in ('+', '-'):
        at = text.rfind(sign, 1)
        if at > 0 and text[at + 1:at + 2].isdigit():
            value = _integer(text[at + 1:])
            return text[:at], value if sign == '+' else -value
    return text, 0


def _i(opcode: int, funct3: int, rd: int, rs1: int, imm: int) -> int:
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode


def _r(funct7: int, rs2: int, rs1: int, funct3: int, rd: int, opcode: int = 0x33) -> int:
    return (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode


def _s(funct3: int, rs1: int, rs2: int, imm: int) -> int:
    return (((imm >> 5) & 0x7F) << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | ((imm & 0x1F) << 7) | 0x23


def _b(funct3: int, rs1: int, rs2: int, offset: int) -> int:
    return ((((offset >> 12) & 1) << 31) | (((offset >> 5) & 0x3F) << 25) | (rs2 << 20) | (rs1 << 15) |
            (funct3 << 12) | (((offset >> 1) & 0xF) << 8) | (((offset >> 11) & 1) << 7) | 0x63)


def _j(rd: int, offset: int) -> int:
    return ((((offset >> 20) & 1) << 31) | (((offset >> 1) & 0x3FF) << 21) | (((offset >> 11) & 1) << 20) |
            (((offset >> 12) & 0xFF) << 12) | (rd << 7) | 0x6F)


def _materialized(rd: int, value: int) -> list[int]:
    words = []
    for index, (op, imm) in enumerate(materialize(value)):
        source = 0 if index == 0 else rd
        if op == 'lui':
            words.append(((imm & 0xFFFFF) << 12) | (rd << 7) | 0x37)
        elif op == 'addiw':
            words.append(_i(0x1B, 0, rd, source, imm))
        elif op in ('slli', 'srli'):
            words.append(_i(0x13, 1 if op == 'slli' else 5, rd, source, imm & 0x3F))
        else:
            words.append(_i(0x13, {'addi': 0, 'xori': 4}[op], rd, source, imm))
    return words


class _Item:
    """One unit of a section's contents before branch layout is final."""
    __slots__ = ('words', 'branch', 'data', 'relocations')

    def __init__(self, words=None, branch=None, data=b'', relocations=()):
        self.words = words or []
        self.branch = branch            # (funct3, rs1, rs2, label) or ('jal', rd, label)
        self.data = data
        self.relocations = list(relocations)   # (offset within item, kind, symbol, addend)


class Assembler:
    def __init__(self):
        self.object = elf.ObjectFile(EM_RISCV, EF_RISCV_FLOAT_ABI_DOUBLE)
        self.items: dict[int, list] = {}
        self.current = self.select('.text', elf.SHT_PROGBITS, elf.SHF_ALLOC | elf.SHF_EXECINSTR)
        self.select('.data', elf.SHT_PROGBITS, elf.SHF_ALLOC | elf.SHF_WRITE)
        self.select('.bss', elf.SHT_NOBITS, elf.SHF_ALLOC | elf.SHF_WRITE)
        self.current = self.object.section_index['.text']
        self.pcrel = 0

    def select(self, name: str, kind: int = elf.SHT_PROGBITS, flags: int = 0) -> int:
        index = self.object.section(name, kind, flags)
        self.items.setdefault(index, [])
        return index

    def emit(self, *words: int, relocations=()) -> None:
        self.items[self.current].append(_Item(list(words), relocations=relocations))

    def label(self, name: str) -> None:
        symbol = self.object.symbol(name)
        if symbol.section is not None:
            raise AssemblyError(f'label {name} defined twice')
        symbol.section = self.current
        # RISC-V relocations name local symbols themselves, not their section
        # symbol plus an offset (the linker may move code between them).
        symbol.keep = not name.startswith('.L')
        section = self.object.sections[self.current]
        if section.kind == elf.SHT_NOBITS:
            symbol.value = section.size
            return
        # The value is set once layout is final: remember the item index.
        symbol.value = len(self.items[self.current])
        self.labels.append(symbol)

    # -- directives ---------------------------------------------------------
    def directive(self, name: str, rest: str) -> None:
        section = self.object.sections[self.current]
        if name == '.text':
            self.current = self.select('.text')
        elif name == '.data':
            self.current = self.select('.data')
        elif name == '.bss':
            self.current = self.select('.bss')
        elif name == '.section':
            parts = [part.strip() for part in rest.split(',')]
            flags = 0
            for letter in (parts[1].strip('"') if len(parts) > 1 else ''):
                flags |= elf.FLAG_LETTERS[letter]
            kind = elf.SHT_NOBITS if len(parts) > 2 and parts[2] == '@nobits' else elf.SHT_PROGBITS
            self.current = self.select(parts[0], kind, flags)
        elif name in ('.globl', '.global'):
            symbol = self.object.symbol(rest.strip())
            if symbol.binding != elf.STB_WEAK:
                symbol.binding = elf.STB_GLOBAL
        elif name == '.weak':
            self.object.symbol(rest.strip()).binding = elf.STB_WEAK
        elif name == '.hidden':
            self.object.symbol(rest.strip()).visibility = elf.STV_HIDDEN
        elif name in ('.extern', '.option'):
            # `.option push/norelax/pop`: nothing here ever relaxes.
            pass
        elif name in ('.dword', '.quad'):
            for item in rest.split(','):
                item = item.strip()
                if item.lstrip('-')[:1].isdigit():
                    self.items[self.current].append(_Item(data=(_integer(item) & (2**64 - 1)).to_bytes(8, 'little')))
                else:
                    symbol, addend = _symbol(item)
                    self.object.symbol(symbol)
                    self.items[self.current].append(_Item(data=bytes(8), relocations=[(0, R_RISCV_64, symbol, addend)]))
        elif name in ('.word', '.long'):
            data = b''.join((_integer(item) & 0xFFFFFFFF).to_bytes(4, 'little') for item in rest.split(','))
            self.items[self.current].append(_Item(data=data))
        elif name == '.byte':
            self.items[self.current].append(_Item(data=bytes(_integer(item) & 0xFF for item in rest.split(','))))
        elif name == '.zero':
            count = _integer(rest)
            if section.kind == elf.SHT_NOBITS:
                section.size += count
            else:
                self.items[self.current].append(_Item(data=bytes(count)))
        elif name in ('.balign', '.p2align', '.align'):
            alignment = _integer(rest.split(',')[0])
            if name != '.balign':
                alignment = 1 << alignment
            section.align = max(section.align, alignment)
            if section.kind == elf.SHT_NOBITS:
                section.size += (-section.size) % alignment
            else:
                self.items[self.current].append(('align', alignment))
        else:
            raise AssemblyError(f'unsupported directive {name}')

    # -- instructions -------------------------------------------------------
    def instruction(self, m: str, ops: list[str]) -> None:
        if m in R_TYPE:
            funct7, funct3 = R_TYPE[m]
            self.emit(_r(funct7, _register(ops[2]), _register(ops[1]), funct3, _register(ops[0])))
        elif m in ('addw', 'subw', 'mulw', 'divw', 'remw', 'sllw', 'srlw', 'sraw'):
            funct7, funct3 = {'addw': (0, 0), 'subw': (0x20, 0), 'mulw': (1, 0), 'divw': (1, 4), 'remw': (1, 6),
                              'sllw': (0, 1), 'srlw': (0, 5), 'sraw': (0x20, 5)}[m]
            self.emit(_r(funct7, _register(ops[2]), _register(ops[1]), funct3, _register(ops[0]), 0x3B))
        elif m in I_TYPE:
            self.emit(_i(0x13, I_TYPE[m], _register(ops[0]), _register(ops[1]), _integer(ops[2])))
        elif m == 'addiw':
            self.emit(_i(0x1B, 0, _register(ops[0]), _register(ops[1]), _integer(ops[2])))
        elif m in SHIFTS:
            funct6, funct3 = SHIFTS[m]
            self.emit(_i(0x13, funct3, _register(ops[0]), _register(ops[1]), (funct6 << 6) | (_integer(ops[2]) & 0x3F)))
        elif m in LOADS:
            offset, base = _memory(ops[1])
            self.emit(_i(0x03, LOADS[m], _register(ops[0]), base, offset))
        elif m in STORES:
            offset, base = _memory(ops[1])
            self.emit(_s(STORES[m], base, _register(ops[0]), offset))
        elif m in BRANCHES:
            self.branch(BRANCHES[m], _register(ops[0]), _register(ops[1]), ops[2])
        elif m in BRANCH_PSEUDOS:
            real, _ = BRANCH_PSEUDOS[m]
            self.branch(BRANCHES[real], _register(ops[1]), _register(ops[0]), ops[2])
        elif m in ZERO_BRANCHES:
            real, zero_first = ZERO_BRANCHES[m]
            register = _register(ops[0])
            if zero_first:
                self.branch(BRANCHES[real], 0, register, ops[1])
            else:
                self.branch(BRANCHES[real], register, 0, ops[1])
        elif m in ('j', 'jal'):
            rd, target = (0 if m == 'j' else 1, ops[0]) if len(ops) == 1 else (_register(ops[0]), ops[1])
            self.object.symbol(_symbol(target)[0])
            self.items[self.current].append(_Item(branch=('jal', rd, target)))
        elif m == 'jalr':
            if len(ops) == 1:
                self.emit(_i(0x67, 0, 1, _register(ops[0]), 0))
            elif len(ops) == 2 and '(' in ops[1]:
                offset, base = _memory(ops[1])
                self.emit(_i(0x67, 0, _register(ops[0]), base, offset))
            else:
                self.emit(_i(0x67, 0, _register(ops[0]), _register(ops[1]), _integer(ops[2]) if len(ops) > 2 else 0))
        elif m == 'jr':
            self.emit(_i(0x67, 0, 0, _register(ops[0]), 0))
        elif m == 'ret':
            self.emit(_i(0x67, 0, 0, 1, 0))
        elif m == 'ecall':
            self.emit(0x00000073)
        elif m == 'ebreak':
            self.emit(0x00100073)
        elif m == 'nop':
            self.emit(_i(0x13, 0, 0, 0, 0))
        elif m == 'mv':
            self.emit(_i(0x13, 0, _register(ops[0]), _register(ops[1]), 0))
        elif m == 'not':
            self.emit(_i(0x13, 4, _register(ops[0]), _register(ops[1]), -1))
        elif m == 'neg':
            self.emit(_r(0x20, _register(ops[1]), 0, 0, _register(ops[0])))
        elif m == 'negw':
            self.emit(_r(0x20, _register(ops[1]), 0, 0, _register(ops[0]), 0x3B))
        elif m == 'seqz':
            self.emit(_i(0x13, 3, _register(ops[0]), _register(ops[1]), 1))
        elif m == 'snez':
            self.emit(_r(0, _register(ops[1]), 0, 3, _register(ops[0])))
        elif m == 'sltz':
            self.emit(_r(0, 0, _register(ops[1]), 2, _register(ops[0])))
        elif m == 'sgtz':
            self.emit(_r(0, _register(ops[1]), 0, 2, _register(ops[0])))
        elif m in ('sgt', 'sgtu'):
            self.emit(_r(0, _register(ops[1]), _register(ops[2]), 2 if m == 'sgt' else 3, _register(ops[0])))
        elif m == 'sext.w':
            self.emit(_i(0x1B, 0, _register(ops[0]), _register(ops[1]), 0))
        elif m == 'li':
            self.emit(*_materialized(_register(ops[0]), _integer(ops[1])))
        elif m == 'lui':
            self.emit(((_integer(ops[1]) & 0xFFFFF) << 12) | (_register(ops[0]) << 7) | 0x37)
        elif m == 'la':
            self.address(_register(ops[0]), ops[1])
        elif m in ('call', 'tail'):
            target, _ = _symbol(ops[0])
            self.object.symbol(target)
            self.items[self.current].append(_Item(branch=('call', 1 if m == 'call' else 6, 1 if m == 'call' else 0, target)))
        elif m in FLOAT_OPS:
            funct7, rs2, funct3 = FLOAT_OPS[m]
            to_float = m in ('fmv.w.x', 'fmv.d.x', 'fcvt.s.l', 'fcvt.d.l')
            rd = _float(ops[0]) if to_float else _register(ops[0])
            rs1 = _register(ops[1]) if to_float else _float(ops[1])
            self.emit(_r(funct7, rs2, rs1, funct3, rd, 0x53))
        else:
            raise AssemblyError(f'unsupported instruction {m}')

    def address(self, rd: int, target: str) -> None:
        """`la rd, sym`: auipc + addi, the low part naming the auipc's label."""
        symbol, addend = _symbol(target)
        self.object.symbol(symbol)
        name = f'.Lpcrel_hi{self.pcrel}'
        self.pcrel += 1
        label = self.object.symbol(name)
        label.keep = True
        label.section = self.current
        label.value = len(self.items[self.current])
        self.labels.append(label)
        self.emit((rd << 7) | 0x17, _i(0x13, 0, rd, rd, 0),
                  relocations=[(0, R_RISCV_PCREL_HI20, symbol, addend), (4, R_RISCV_PCREL_LO12_I, name, 0)])

    def branch(self, funct3: int, rs1: int, rs2: int, target: str) -> None:
        self.object.symbol(target)
        self.items[self.current].append(_Item(branch=(funct3, rs1, rs2, target)))

    # -- layout -------------------------------------------------------------
    def layout(self) -> None:
        """Lay out each section; a conditional branch that does not reach its
        label becomes the inverted branch over a `jal`, until nothing changes."""
        for index, items in self.items.items():
            section = self.object.sections[index]
            if section.kind == elf.SHT_NOBITS:
                continue
            labels = {symbol.name: symbol.value for symbol in self.labels if symbol.section == index}
            long_branches: set[int] = set()
            while True:
                offsets = self.offsets(items, long_branches)
                changed = False
                for position, item in enumerate(items):
                    if isinstance(item, tuple) or item.branch is None or item.branch[0] in ('jal', 'call'):
                        continue
                    target = labels.get(item.branch[3])
                    if target is None or position in long_branches:
                        continue
                    distance = offsets[target] - offsets[position]
                    if not -4096 <= distance <= 4094:
                        long_branches.add(position)
                        changed = True
                if not changed:
                    break
            if long_branches and any(isinstance(item, tuple) for item in items):
                # The backend never aligns code; the native writer relaxes
                # in place and cannot re-pad.
                raise AssemblyError(f'a relaxed branch in code with alignment padding ({section.name})')
            offsets = self.offsets(items, long_branches)
            data = bytearray()
            for position, item in enumerate(items):
                if isinstance(item, tuple):
                    padding = (-len(data)) % item[1]
                    if section.flags & elf.SHF_EXECINSTR and padding % 4 == 0:
                        data.extend(struct.pack('<I', 0x13) * (padding // 4))
                    else:
                        data.extend(bytes(padding))
                    continue
                start = len(data)
                for offset, kind, symbol, addend in item.relocations:
                    section.relocations.append(elf.Relocation(start + offset, kind, symbol, addend))
                if item.branch is not None:
                    data.extend(self.encode_branch(item, position, offsets, labels, long_branches, start, section))
                elif item.words:
                    data.extend(struct.pack(f'<{len(item.words)}I', *item.words))
                else:
                    data.extend(item.data)
            section.data = data
            for symbol in self.labels:
                if symbol.section == index:
                    symbol.value = offsets[symbol.value]

    @staticmethod
    def offsets(items: list, long_branches: set[int]) -> list[int]:
        """The offset of every item (and one past the end), for this layout."""
        offsets = []
        at = 0
        for position, item in enumerate(items):
            offsets.append(at)
            if isinstance(item, tuple):
                at += (-at) % item[1]
            elif item.branch is not None:
                at += 8 if position in long_branches or item.branch[0] == 'call' else 4
            elif item.words:
                at += 4 * len(item.words)
            else:
                at += len(item.data)
        offsets.append(at)
        return offsets

    def encode_branch(self, item, position, offsets, labels, long_branches, start, section) -> bytes:
        branch = item.branch
        here = offsets[position]
        if branch[0] == 'call':
            # auipc + jalr; a local function in this section is reached
            # without a relocation.
            _, link, rd, target = branch
            if target in labels and self.object.symbols[target].binding == elf.STB_LOCAL:
                distance = offsets[labels[target]] - here
                high = ((distance + 0x800) >> 12) & 0xFFFFF
                return struct.pack('<II', (high << 12) | (link << 7) | 0x17, _i(0x67, 0, rd, link, distance))
            section.relocations.append(elf.Relocation(start, R_RISCV_CALL_PLT, target, 0))
            return struct.pack('<II', (link << 7) | 0x17, _i(0x67, 0, rd, link, 0))
        if branch[0] == 'jal':
            _, rd, target = branch
            name, addend = _symbol(target)
            if name in labels and addend == 0:
                return struct.pack('<I', _j(rd, offsets[labels[name]] - here))
            self.object.symbol(name)
            section.relocations.append(elf.Relocation(start, R_RISCV_JAL, name, addend))
            return struct.pack('<I', _j(rd, 0))
        funct3, rs1, rs2, target = branch
        if target not in labels:
            self.object.symbol(target)
            section.relocations.append(elf.Relocation(start, R_RISCV_BRANCH, target, 0))
            return struct.pack('<I', _b(funct3, rs1, rs2, 0))
        distance = offsets[labels[target]] - here
        if position in long_branches:
            # The inverted branch skips the jal that reaches the label.
            return struct.pack('<II', _b(funct3 ^ 1, rs1, rs2, 8), _j(0, distance - 4))
        return struct.pack('<I', _b(funct3, rs1, rs2, distance))

    # -- driver -------------------------------------------------------------
    def assemble(self, text: str) -> bytes:
        self.labels: list = []
        for line_number, raw in enumerate(text.split('\n'), 1):
            line = raw.split('#', 1)[0].strip()
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
                self.instruction(head, [part.strip() for part in rest.split(',')] if rest.strip() else [])
            except (AssemblyError, ValueError, KeyError, IndexError) as error:
                raise AssemblyError(f'line {line_number}: {raw.strip()}: {error}') from None
        self.layout()
        return self.object.write()


def assemble(text: str) -> bytes:
    """The ELF object for RISC-V assembly `text` from the µDewy riscv backend."""
    return Assembler().assemble(text)


if __name__ == '__main__':
    # `python -m udewy.backend.riscv_object in.s out.o`: the direct path on its
    # own, for comparing it with an assembler.
    import sys
    if len(sys.argv) != 3:
        sys.exit('usage: python -m udewy.backend.riscv_object in.s out.o')
    with open(sys.argv[1]) as source, open(sys.argv[2], 'wb') as output:
        output.write(assemble(source.read()))
