# Stopping to Look: `$breakpoint`

When a program does something you did not expect, the quickest question is "what are the values *here*?" Put `$breakpoint` on that line:

```dewy
let describe = (hits:array<Hit> label:string):>int64 => {
    let total:int64 = 0
    loop h in hits {
        total += (h.length transmute int64) * 3
        $breakpoint
    }
    return total
}
```

Each time the program reaches it, it prints the function's live bindings and waits:

```text
── breakpoint at hits.dewy:5 ──
  hits = [Hit[length=3 name="a"] Hit[length=10 name="b"]]
  label = "run"
  total = 9
  h = Hit[length=3 name="a"]
>>>
```

Press Enter (or type `\c`) to continue to the next stop, `\q` to quit, `\h` for the list. Commands start with a backslash because the plain prompt is reserved for expressions: a compiled program cannot evaluate a typed-in expression yet, so for now it says so. Output that is not a terminal (a pipe, `/dev/null`) continues on its own, so breakpoints left in do not hang an unattended run.

For stepping through code, breakpoints on lines you did not edit, and the call stack, run the program under a debugger:

```bash
dewy debug hits.dewy
```

That builds the program and opens gdb (or lldb) on it. The debugger knows Dewy files and lines — `b hits.dewy:5`, `n`, `bt` — and a `$breakpoint` in the program stops the debugger on that line instead of prompting. It does not yet show Dewy values on its own (`p total` prints a bare number; strings and arrays are pointers), which is why `$breakpoint` prints them for you. See [Debugging](../../reference/debugging.html) in the Reference for the details.
