"""lldb support for Dewy programs: values shown the Dewy way.

`dewy debug` loads this script. Every Dewy local reaches the debugger as a
word (its frame slot) whose DWARF type is named after the compiler's
formatter for the variable's Dewy type (`__dewy_debug_show_N`, a function
`(v:T):>int64` compiled into the program). The summary provider here calls
that formatter in the stopped process and reads the text it returns — a
`[length][bytes]` block — so `frame variable`, `p hits`, and an IDE's
variables pane show `[Hit[length=3 name="a"] …]` instead of a pointer.
"""
from __future__ import annotations

import lldb

FORMATTER_PREFIX = '__dewy_debug_show_'
TEXT_LIMIT = 65536


def _formatter_address(target: lldb.SBTarget, name: str) -> int | None:
    for context in target.FindSymbols(name):
        symbol = context.GetSymbol()
        if symbol.IsValid():
            return symbol.GetStartAddress().GetLoadAddress(target)
    return None


def _formatter_name(type_: lldb.SBType) -> str | None:
    """The formatter behind a variable's type: the typedef chain is
    `dewy type -> formatter -> int64`, and the summary may be asked about
    either of the first two."""
    while type_.IsValid() and type_.IsTypedefType():
        if type_.GetName().startswith(FORMATTER_PREFIX):
            return type_.GetName()
        type_ = type_.GetTypedefedType()
    return None


def dewy_summary(valobj: lldb.SBValue, internal_dict: dict) -> str:
    """The Dewy text of a local: its formatter, called on the value's word."""
    type_name = _formatter_name(valobj.GetType())
    if type_name is None:
        return ''
    target = valobj.GetTarget()
    process = valobj.GetProcess()
    frame = valobj.GetFrame()
    address = _formatter_address(target, type_name)
    if address is None or not frame.IsValid():
        return '<no formatter>'
    word = valobj.GetValueAsUnsigned()
    options = lldb.SBExpressionOptions()
    options.SetIgnoreBreakpoints(True)
    options.SetTimeoutInMicroSeconds(2_000_000)
    options.SetUnwindOnError(True)
    result = frame.EvaluateExpression(f'((unsigned long (*)(unsigned long)){address})({word}UL)', options)
    if not result.IsValid() or result.GetError().Fail():
        return '<unavailable>'
    block = result.GetValueAsUnsigned()
    error = lldb.SBError()
    length = process.ReadUnsignedFromMemory(block, 8, error)
    if error.Fail() or length > TEXT_LIMIT:
        return '<unavailable>'
    if length == 0:
        return '""'
    data = process.ReadMemory(block + 8, length, error)
    if error.Fail():
        return '<unavailable>'
    return data.decode('utf-8', errors='replace')


def __lldb_init_module(debugger: lldb.SBDebugger, internal_dict: dict) -> None:
    # the summary alone: the word behind a Dewy value is not the value
    # matched on the formatter typedef; `-C true` cascades to the Dewy-named typedef of it
    debugger.HandleCommand(f'type summary add -w dewy -v -C true -F dewy_lldb.dewy_summary -x "^{FORMATTER_PREFIX}"')
    debugger.HandleCommand('type category enable dewy')
