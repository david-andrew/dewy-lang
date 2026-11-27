# Stopping to Look

## Print it

`printl` prints any value as its literal: numbers, strings in quotes inside containers, arrays, records, dictionaries and optionals. That alone answers most questions.

<!-- dewy-example: {"mode": "run", "stdout": "[name=\"ada\" scores=[72 95]]\n[\"x\" -> 1]\nnone\n"} -->
```dewy
player = [name="ada" scores=[72 95]]
printl(player)
printl(["x" -> 1])
printl([3 1 4].get(7))
```

## Pause with `$breakpoint`

Put `$breakpoint` on a line of its own. When the program reaches it, it prints where it is and every live binding of the function, then waits at a `>>>` prompt: press Enter (or `\c`) to continue, `\q` to quit. At the end of input (`/dev/null`, or a pipe that runs dry) it continues, so a forgotten breakpoint does not hang a script.

<!-- dewy-example: {"mode": "check"} -->
```dewy
average = (xs:array<int>) => {
    let total = 0
    loop x in xs total += x
    $breakpoint
    if xs.length =? 0 return none
    total / xs.length
}
printl(average([3 4 8]))
```

```text
── breakpoint at average.dewy:4 ──
  xs = [3 4 8]
  total = 15
>>>
```

## Use a debugger

Build with `-g` for full debug information and use gdb, lldb or the VS Code extension (through CodeLLDB):

```sh
dewy build average.dewy -g -o average-debug
gdb ./average-debug
```

The toolchain's `lib/debug/dewy_gdb.py` (load it with gdb's `source`) and `dewy_lldb.py` (lldb's `command script import`) show values the way Dewy prints them. `dewy --print-lib` prints where the library folder is.

## Ask the compiler

Most surprises in Dewy are compile errors, and they say a lot: the error for an unproven index names the missing fact, shows values that would break it, and suggests fixes. When you have opted into runtime checks with `$runtime_checks`, `dewy check --obligations file.dewy` lists every place that still compiles to a check, so you can turn them into proofs one at a time. A failing runtime check reports the requirement and the values it saw, such as ``index 5 out of bounds (length 3)``, and exits with status 101.
