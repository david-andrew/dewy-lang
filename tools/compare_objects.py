#!/usr/bin/env python3
"""Compare two relocatable objects symbol by symbol (see ROADMAP "Direct binary fast path").

    tools/compare_objects.py reference.o candidate.o

The reference is the assembler's object and the candidate a direct object.
Byte identity is not required; semantic equality per symbol is:

- per function, the same instruction sequence: mnemonic and operands as
  `objdump` prints them, with branch targets as the index of the instruction
  they land on, and each relocation's type, symbol and addend attached to
  its instruction (an x86 rel8 and rel32 branch to one label are the same,
  and a run of NOPs is alignment padding whatever its encoding);
- initialized data bytes and data relocations (type, symbol, addend);
  NOBITS sections by size only;
- section type, flags and alignment;
- symbol binding, visibility, type, size and section, and no `.L` labels.

Exits 1 and prints the first differences when the objects disagree.
"""
from __future__ import annotations

import re
import struct
import subprocess
import sys
from collections import defaultdict

INSTRUCTION = re.compile(r'^\s*([0-9a-f]+):\s+(.*)$')
RELOCATION = re.compile(r'^\s*([0-9a-f]+):\s+(R_\w+)\s+(.*)$')
# With `-w` objdump appends an instruction's relocations to its line.
INLINE_RELOCATION = re.compile(r'\s+([0-9a-f]+):\s+(R_\w+)\s+(\S+)')
# Sections an assembler adds on its own that no backend asks for: gas marks
# the x86 ISA level used. A direct object may omit them.
ASSEMBLER_NOTES = {'.note.gnu.property'}
FUNCTION = re.compile(r'^[0-9a-f]+ <(.+)>:$')
SECTION = re.compile(r'^Disassembly of section (.+):$')
BRANCH_TARGET = re.compile(r'^([0-9a-f]+) <([^>]+)>$')
# Relative targets objdump prints for a branch whose field holds a relocation.
PLACEHOLDER = re.compile(r'^[0-9a-f]+ <[^>]*>$')
SHORT_OR_NEAR = {'jmp', 'call'}


def _run(*command: str) -> str:
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


def _normalize_addend(target: str) -> str:
    """`sym-0x4` / `sym+0x8` / `.data..str0+0x8` in one spelling."""
    match = re.match(r'^(.*?)([+-]0x[0-9a-f]+)?$', target.strip())
    name, addend = match.group(1), match.group(2)
    value = int(addend.replace('0x', ''), 16) if addend else 0
    return f'{name}{value:+d}'


def functions(path: str) -> dict[str, list[tuple]]:
    """Per function symbol: its instructions, normalized."""
    output = _run('objdump', '-dr', '--no-show-raw-insn', '-w', path)
    result: dict[str, list[list]] = {}
    current: list | None = None
    addresses: list[int] = []
    for line in output.split('\n'):
        match = FUNCTION.match(line)
        if match:
            current = result.setdefault(match.group(1), [])
            addresses = []
            continue
        if current is None or not line.strip():
            continue
        relocation = RELOCATION.match(line)
        if relocation:
            if current:
                current[-1][2].append((relocation.group(2), _normalize_addend(relocation.group(3))))
            continue
        instruction = INSTRUCTION.match(line)
        if instruction:
            address = int(instruction.group(1), 16)
            body = instruction.group(2)
            inline = [(match.group(2), _normalize_addend(match.group(3))) for match in INLINE_RELOCATION.finditer(body)]
            body = INLINE_RELOCATION.split(body)[0] if inline else body
            text = ' '.join(body.split())
            addresses.append(address)
            current.append([address, text, inline])
    normalized: dict[str, list[tuple]] = {}
    for name, instructions in result.items():
        # Collapse alignment padding first: gas picks multi-byte NOPs (the
        # choice varies by version), so any run of NOPs is the same padding.
        # Branch targets then index this collapsed sequence.
        kept: list[tuple[int, str, str, list]] = []
        index_of: dict[int, int] = {}
        for address, text, relocations in instructions:
            mnemonic, _, operands = text.partition(' ')
            padding = mnemonic.startswith('nop') or (mnemonic in ('data16', 'cs') and 'nop' in operands) or (
                mnemonic == 'xchg' and operands == '%ax,%ax')
            if padding:
                mnemonic, operands = '<padding>', ''
                if kept and kept[-1][1] == '<padding>':
                    index_of[address] = len(kept) - 1
                    continue
            index_of[address] = len(kept)
            kept.append((address, mnemonic, operands, relocations))
        entries = []
        for _, mnemonic, operands, relocations in kept:
            if relocations and PLACEHOLDER.match(operands):
                operands = '<relocated>'
            else:
                target = BRANCH_TARGET.match(operands)
                if target and mnemonic.startswith(('j', 'call')):
                    destination = int(target.group(1), 16)
                    operands = f'<insn {index_of.get(destination, "?")}>'
            # RIP-relative operands print the resolved address of a relocated
            # field (0x0); the relocation carries the meaning.
            if relocations:
                operands = re.sub(r'0x[0-9a-f]+\(%rip\)', '(%rip)', operands)
                operands = re.sub(r'\s*#.*$', '', operands)
            entries.append((mnemonic, operands, tuple(relocations)))
        normalized[name] = entries
    return normalized


def sections(path: str) -> dict[str, tuple]:
    output = _run('readelf', '-SW', path)
    result = {}
    for line in output.split('\n'):
        match = re.match(r'^\s*\[\s*\d+\]\s+(\S+)\s+(\S+)\s+[0-9a-f]+\s+[0-9a-f]+\s+([0-9a-f]+)\s+[0-9a-f]+\s+(\S*)\s+\d+\s+\d+\s+(\d+)$', line)
        if not match:
            continue
        name, kind, size, flags, align = match.groups()
        if kind in ('RELA', 'SYMTAB', 'STRTAB') or name in ASSEMBLER_NOTES or (
                name in ('.text', '.data', '.bss') and int(size, 16) == 0):
            continue
        result[name] = (kind, flags, int(align), int(size, 16) if kind == 'NOBITS' else None)
    return result


def _section_bytes(path: str) -> dict[str, bytes]:
    """Contents of every PROGBITS section, read from the ELF file itself."""
    raw = open(path, 'rb').read()
    shoff, = struct.unpack_from('<Q', raw, 0x28)
    shentsize, shnum, shstrndx = struct.unpack_from('<HHH', raw, 0x3A)
    # Extended numbering: the real count and string table index are in
    # section header 0 (sh_size, sh_link).
    first = struct.unpack_from('<IIQQQQIIQQ', raw, shoff)
    shnum = shnum or first[5]
    shstrndx = first[6] if shstrndx == 0xFFFF else shstrndx
    headers = [struct.unpack_from('<IIQQQQIIQQ', raw, shoff + index * shentsize) for index in range(shnum)]
    names_offset = headers[shstrndx][4]
    result = {}
    for name, kind, _, _, offset, size, *_ in headers:
        if kind != 1:
            continue
        end = raw.index(b'\0', names_offset + name)
        result[raw[names_offset + name:end].decode()] = raw[offset:offset + size]
    return result


def data(path: str, names: list[str]) -> dict[str, tuple]:
    """Initialized bytes and relocations of non-executable PROGBITS sections."""
    relocations: dict[str, list] = defaultdict(list)
    current = None
    for line in _run('readelf', '-rW', path).split('\n'):
        header = re.match(r"^Relocation section '\.rela(.+)' at", line)
        if header:
            current = header.group(1)
            continue
        entry = re.match(r'^([0-9a-f]+)\s+[0-9a-f]+\s+(R_\w+)\s+[0-9a-f]+\s+(\S+)\s*([+-])\s*([0-9a-f]+)$', line)
        if entry and current:
            offset, kind, symbol, sign, addend = entry.groups()
            value = int(addend, 16) * (1 if sign == '+' else -1)
            relocations[current].append((int(offset, 16), kind, f'{symbol}{value:+d}'))
    contents = _section_bytes(path)
    return {name: (contents.get(name), tuple(relocations.get(name, ()))) for name in names}


def symbols(path: str) -> dict[str, tuple]:
    result = {}
    for line in _run('readelf', '-sW', path).split('\n'):
        match = re.match(r'^\s*\d+:\s+([0-9a-f]+)\s+(\d+)\s+(\w+)\s+(\w+)\s+(\w+)\s+(\S+)\s*(\S*)$', line)
        if not match:
            continue
        value, size, kind, binding, visibility, index, name = match.groups()
        if kind == 'SECTION' or kind == 'FILE' or not name:
            continue
        result[name] = (kind, binding, visibility, int(size), index == 'UND')
    return result


def compare(reference: str, candidate: str, limit: int = 20) -> list[str]:
    problems: list[str] = []
    reference_sections, candidate_sections = sections(reference), sections(candidate)
    for name in sorted(set(reference_sections) | set(candidate_sections)):
        left, right = reference_sections.get(name), candidate_sections.get(name)
        if left != right:
            problems.append(f'section {name}: {left} != {right}')
    reference_symbols, candidate_symbols = symbols(reference), symbols(candidate)
    for name in sorted(set(reference_symbols) | set(candidate_symbols)):
        if name.startswith('.L') and name in candidate_symbols:
            problems.append(f'symbol {name}: temporary label in the symbol table')
            continue
        left, right = reference_symbols.get(name), candidate_symbols.get(name)
        if left != right:
            problems.append(f'symbol {name}: {left} != {right}')
    data_sections = [name for name, (kind, flags, _, _) in reference_sections.items()
                     if kind == 'PROGBITS' and 'X' not in flags and 'A' in flags]
    reference_data, candidate_data = data(reference, data_sections), data(candidate, data_sections)
    for name in data_sections:
        if reference_data[name] != candidate_data.get(name):
            problems.append(f'data {name} differs')
    reference_functions, candidate_functions = functions(reference), functions(candidate)
    for name in sorted(set(reference_functions) | set(candidate_functions)):
        left, right = reference_functions.get(name), candidate_functions.get(name)
        if left == right:
            continue
        if left is None or right is None:
            problems.append(f'function {name}: present in only one object')
            continue
        for index, (a, b) in enumerate(zip(left, right)):
            if a != b:
                problems.append(f'function {name} instruction {index}: {a} != {b}')
                break
        else:
            problems.append(f'function {name}: {len(left)} != {len(right)} instructions')
        if len(problems) >= limit:
            break
    return problems


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__.strip().split('\n\n')[1].strip(), file=sys.stderr)
        return 2
    problems = compare(sys.argv[1], sys.argv[2])
    for problem in problems[:20]:
        print(problem)
    if problems:
        print(f'{len(problems)} difference(s)' + (' (first 20 shown)' if len(problems) > 20 else ''))
        return 1
    print('objects agree')
    return 0


if __name__ == '__main__':
    sys.exit(main())
