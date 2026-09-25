# µDewy bytecode (`.ubc`)

A recording of the calls the µDewy parser makes on its backend (see ROADMAP
"Direct binary fast path"). A player decodes each operation and makes the
same call on a live backend, so a module can reach code generation without
µDewy source text, tokens or a parse. Both µDewy compilers read and write
the same format: the Python recorder and player in `udewy/stream.py`, and
the native ones in `udewy/bootstrap/stream.udewy`.

A stream is only valid for the target it was recorded for: builtin constants
such as syscall numbers are folded before the calls are made, and
target-conditional imports are resolved by then.

## Encoding

- `u`: unsigned LEB128.
- `s`: signed value, zigzag-encoded then LEB128.
- `str`: `u` byte length, then the bytes.
- `ostr`: `u` 0 for none, otherwise byte length + 1, then the bytes.

A file is the magic `UBC1`, a `u` count of link artifacts followed by one
`str` path each, then operations until `finish_module`. Each operation is a
one-byte opcode followed by its operands.

## Ids

Operations that create something (a function, global, string, static
block, local slot, or and/or split label) end with the id the recorder saw
(`u`). A player maps that recorded id to whatever its backend returned, in
one table per id space: functions, globals, strings, statics, slots, and
split labels. A producer other than the recorder (Dewy) may number ids any
way it likes within each space.

A stable value is `u` kind followed by its payload. Kind 1 is an integer
(`s`), kind 2 a function id, kind 3 a string id, and kind 4 a static id
(`u`). The player turns the non-integer kinds into its backend's reference
value (`function_ref`, `string_ref`, `static_ref`).

## Operations

| op | name | operands | creates |
|----|------|----------|---------|
| 1 | begin_module | | |
| 2 | finish_module | | |
| 3 | set_module_init | `ostr` name | |
| 4 | set_imported_sources | `u` count, `str` each | |
| 5 | mark_location | `str` path, `u` line, `u` column | |
| 6 | note_local | slot, `str` name, `str` type, `ostr` formatter, `u` parameter | |
| 7 | begin_scope | | |
| 8 | end_scope | | |
| 9 | intern_string | `str` bytes | string |
| 10 | define_global | `ostr` name, stable value | global |
| 11 | declare_extern_global | `str` name | global |
| 12 | intern_static | `u` size | static |
| 13 | intern_words | `u` count, stable value each | static |
| 14 | push_string_ref | string | |
| 15 | push_global_ref | global | |
| 16 | push_static_ref | static | |
| 17 | load_global | global | |
| 18 | store_global | global | |
| 19 | declare_function | `ostr` name, `u` parameters | function |
| 20 | bind_extern_function | function, `str` name | |
| 21 | declare_extern_function | `str` name, `u` parameters | function |
| 22 | begin_function | function, `ostr` name, `u` parameters, `u` is_main | |
| 23 | end_function | | |
| 24 | set_reachable_functions | `u` count, function each | |
| 25 | load_param | `u` index | |
| 26 | alloc_local | | slot |
| 27 | load_local | slot | |
| 28 | store_local | slot | |
| 29 | push_const_i64 | `s` value | |
| 30 | push_void | | |
| 31 | push_fn_ref | function | |
| 32 | pop_value | | |
| 33 | save_value | | |
| 34 | restore_value | | |
| 35 | unary_op | `u` token kind | |
| 36 | binary_op | `u` token kind | |
| 37 | binary_immediate | `u` token kind, `s` value | |
| 38 | begin_if | | |
| 39 | begin_else | | |
| 40 | end_if | | |
| 41 | begin_loop | | |
| 42 | begin_loop_body | | |
| 43 | end_loop | | |
| 44 | emit_break | | |
| 45 | emit_continue | | |
| 46 | cond_and_split | | split label |
| 47 | cond_and_join | split label | |
| 48 | cond_or_split | | split label |
| 49 | cond_or_join | split label | |
| 50 | emit_return | | |
| 51 | call_direct | function, `u` arguments | |
| 52 | call_indirect | `u` arguments | |
| 53 | emit_intrinsic | `str` name, `u` arguments, `u` static count, (`u` index, `s` value) each | |

Token kinds are the µDewy tokenizer's (`t1`), which both compilers number
identically. Id operands are `u`.
