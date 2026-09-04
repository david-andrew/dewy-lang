"""gdb support for Dewy programs: values shown the Dewy way.

`dewy debug` loads this script (`gdb -x`). Every Dewy local reaches the
debugger as a word whose DWARF type is named after the compiler's formatter
for the variable's Dewy type (`__dewy_debug_show_N`, a function
`(v:T):>int64` compiled into the program). The pretty-printer here calls that
formatter in the stopped process and reads the text it returns — a
`[length][bytes]` block — so `info locals` and `p hits` show
`[Hit[length=3 name="a"] …]` instead of a number. See tools/dewy_lldb.py for
the lldb counterpart.
"""
from __future__ import annotations

import gdb

FORMATTER_PREFIX = '__dewy_debug_show_'
TEXT_LIMIT = 65536


class DewyValuePrinter:
    def __init__(self, value: gdb.Value, formatter: str) -> None:
        self.value = value
        self.formatter = formatter

    def to_string(self) -> str:
        try:
            word = int(self.value)
            symbol = gdb.lookup_global_symbol(self.formatter) or gdb.lookup_symbol(self.formatter)[0]
            if symbol is None:
                address = int(gdb.parse_and_eval(f'(unsigned long)&{self.formatter}'))
            else:
                address = int(symbol.value().address)
            block = int(gdb.parse_and_eval(f'((unsigned long (*)(unsigned long)){address})({word}UL)'))
            inferior = gdb.selected_inferior()
            length = int.from_bytes(bytes(inferior.read_memory(block, 8)), 'little')
            if length > TEXT_LIMIT:
                return '<unavailable>'
            if length == 0:
                return '""'
            return bytes(inferior.read_memory(block + 8, length)).decode('utf-8', errors='replace')
        except gdb.error:
            return '<unavailable>'


def lookup(value: gdb.Value):
    # the typedef chain is `dewy type -> formatter -> int64`
    type_ = value.type
    while type_.code == gdb.TYPE_CODE_TYPEDEF:
        if type_.name is not None and type_.name.startswith(FORMATTER_PREFIX):
            return DewyValuePrinter(value, type_.name)
        type_ = type_.target()
    return None


gdb.pretty_printers.append(lookup)
