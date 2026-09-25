"""ELF64 relocatable object files, written without an assembler.

The direct-object backends (see ROADMAP "Direct binary fast path") encode
their instructions themselves and hand the bytes to this writer: named
sections with flags and alignment, a symbol table, and RELA relocations.
`ld` still links the result. Mirrors `udewy/bootstrap/backend/elf.udewy`.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

SHT_PROGBITS = 1
SHT_SYMTAB = 2
SHT_STRTAB = 3
SHT_RELA = 4
SHT_NOBITS = 8

SHF_WRITE = 0x1
SHF_ALLOC = 0x2
SHF_EXECINSTR = 0x4
SHF_INFO_LINK = 0x40
SHF_GNU_RETAIN = 0x200000

STB_LOCAL = 0
STB_GLOBAL = 1
STB_WEAK = 2
STT_NOTYPE = 0
STT_SECTION = 3
STV_DEFAULT = 0
STV_HIDDEN = 2

ELFOSABI_GNU = 3

EM_X86_64 = 62
EM_AARCH64 = 183
EM_RISCV = 243

# Section flag letters as written after `.section name,"..."`.
FLAG_LETTERS = {'a': SHF_ALLOC, 'w': SHF_WRITE, 'x': SHF_EXECINSTR, 'R': SHF_GNU_RETAIN}


@dataclass
class Relocation:
    offset: int
    kind: int
    symbol: str
    addend: int


@dataclass
class Section:
    name: str
    kind: int
    flags: int
    data: bytearray = field(default_factory=bytearray)
    size: int = 0              # NOBITS sections only
    align: int = 1
    relocations: list[Relocation] = field(default_factory=list)

    def length(self) -> int:
        return self.size if self.kind == SHT_NOBITS else len(self.data)


@dataclass
class Symbol:
    name: str
    section: int | None = None     # index into `ObjectFile.sections`; None when undefined
    value: int = 0
    binding: int = STB_LOCAL
    visibility: int = STV_DEFAULT
    # A `.L` label kept in the symbol table and referenced by name (RISC-V
    # %pcrel_lo relocations name their auipc's label).
    keep: bool = False


class ObjectFile:
    """Sections and symbols of one relocatable object, in definition order."""

    def __init__(self, machine: int, flags: int = 0):
        self.machine = machine
        self.flags = flags      # e_flags: the RISC-V float ABI
        self.sections: list[Section] = []
        self.section_index: dict[str, int] = {}
        self.symbols: dict[str, Symbol] = {}

    def section(self, name: str, kind: int = SHT_PROGBITS, flags: int = 0) -> int:
        index = self.section_index.get(name)
        if index is None:
            index = len(self.sections)
            self.sections.append(Section(name, kind, flags))
            self.section_index[name] = index
        return index

    def symbol(self, name: str) -> Symbol:
        symbol = self.symbols.get(name)
        if symbol is None:
            symbol = self.symbols[name] = Symbol(name)
        return symbol

    def write(self) -> bytes:
        """The object file: ELF header, section contents, then section headers."""
        # A relocation target defined nowhere in this object is an undefined
        # global (an `extern`, or a symbol from a link artifact).
        for section in self.sections:
            for relocation in section.relocations:
                target = self.symbol(relocation.symbol)
                if target.section is None:
                    target.binding = max(target.binding, STB_GLOBAL)
        # A section symbol per section, then local symbols, then global/weak
        # ones: the symbol table's `sh_info` is the index of the first
        # non-local symbol. `.L` labels are assembler temporaries and stay
        # out of the table (unless kept); references to other local labels go
        # through section symbols.
        named = [symbol for symbol in self.symbols.values() if symbol.keep or not symbol.name.startswith('.L')]
        locals_ = [symbol for symbol in named if symbol.binding == STB_LOCAL and symbol.section is not None]
        globals_ = [symbol for symbol in named if symbol.binding != STB_LOCAL or symbol.section is None]
        strtab = bytearray(b'\0')
        string_offsets: dict[str, int] = {}

        def string(text: str) -> int:
            offset = string_offsets.get(text)
            if offset is None:
                offset = string_offsets[text] = len(strtab)
                strtab.extend(text.encode() + b'\0')
            return offset

        # Section header indices: 0 is null, then content sections, then the
        # relocation sections, symtab, strtab and shstrtab.
        content_index = {index: index + 1 for index in range(len(self.sections))}
        symtab = bytearray(24)
        symbol_index: dict[str, int] = {}
        section_symbol_index: dict[int, int] = {}
        for index in range(len(self.sections)):
            section_symbol_index[index] = len(symtab) // 24
            symtab += struct.pack('<IBBHQQ', 0, STT_SECTION, 0, content_index[index], 0, 0)
        for symbol in locals_ + globals_:
            symbol_index[symbol.name] = len(symtab) // 24
            info = (symbol.binding << 4) | STT_NOTYPE
            shndx = 0 if symbol.section is None else content_index[symbol.section]
            symtab += struct.pack('<IBBHQQ', string(symbol.name), info, symbol.visibility, shndx, symbol.value, 0)
        first_global = 1 + len(self.sections) + len(locals_)

        relocation_sections: list[tuple[int, bytearray]] = []
        for index, section in enumerate(self.sections):
            if not section.relocations:
                continue
            table = bytearray()
            for relocation in section.relocations:
                target = self.symbols.get(relocation.symbol)
                addend = relocation.addend
                # A reference to a label with no symbol-table entry (`.L`
                # temporaries, local labels) goes through its section symbol.
                if target is not None and target.section is not None and (
                        target.binding == STB_LOCAL) and not target.keep:
                    entry = section_symbol_index[target.section]
                    addend += target.value
                else:
                    entry = symbol_index.get(relocation.symbol)
                    if entry is None:
                        raise ValueError(f'relocation against unknown symbol {relocation.symbol}')
                table += struct.pack('<QQq', relocation.offset, (entry << 32) | relocation.kind, addend)
            relocation_sections.append((index, table))

        shstrtab = bytearray(b'\0')

        def section_name(text: str) -> int:
            offset = len(shstrtab)
            shstrtab.extend(text.encode() + b'\0')
            return offset

        body = bytearray(64)
        headers: list[bytes] = [bytes(64)]

        def place(data: bytes | bytearray, align: int) -> int:
            padding = (-len(body)) % max(align, 1)
            body.extend(bytes(padding))
            offset = len(body)
            body.extend(data)
            return offset

        for section in self.sections:
            name = section_name(section.name)
            if section.kind == SHT_NOBITS:
                offset = len(body)
                size = section.size
            else:
                offset = place(section.data, section.align)
                size = len(section.data)
            headers.append(struct.pack('<IIQQQQIIQQ', name, section.kind, section.flags, 0, offset, size,
                                       0, 0, section.align, 0))
        symtab_header_index = 1 + len(self.sections) + len(relocation_sections)
        for index, table in relocation_sections:
            name = section_name('.rela' + self.sections[index].name)
            offset = place(table, 8)
            headers.append(struct.pack('<IIQQQQIIQQ', name, SHT_RELA, SHF_INFO_LINK, 0, offset, len(table),
                                       symtab_header_index, content_index[index], 8, 24))
        name = section_name('.symtab')
        offset = place(symtab, 8)
        headers.append(struct.pack('<IIQQQQIIQQ', name, SHT_SYMTAB, 0, 0, offset, len(symtab),
                                   symtab_header_index + 1, first_global, 8, 24))
        name = section_name('.strtab')
        offset = place(strtab, 1)
        headers.append(struct.pack('<IIQQQQIIQQ', name, SHT_STRTAB, 0, 0, offset, len(strtab), 0, 0, 1, 0))
        name = section_name('.shstrtab')
        shstrtab_index = len(headers)
        offset = place(shstrtab, 1)
        headers.append(struct.pack('<IIQQQQIIQQ', name, SHT_STRTAB, 0, 0, offset, len(shstrtab), 0, 0, 1, 0))

        header_offset = place(b'', 8)
        # SHF_GNU_RETAIN is a GNU extension: an object using it declares the
        # GNU OS/ABI, as gas does, or `ld --gc-sections` ignores the flag.
        gnu = any(section.flags & SHF_GNU_RETAIN for section in self.sections)
        ident = b'\x7fELF' + bytes([2, 1, 1, ELFOSABI_GNU if gnu else 0]) + bytes(8)
        body[0:64] = ident + struct.pack('<HHIQQQIHHHHHH', 1, self.machine, 1, 0, 0, header_offset, self.flags,
                                         64, 0, 0, 64, len(headers), shstrtab_index)
        for header in headers:
            body.extend(header)
        return bytes(body)
