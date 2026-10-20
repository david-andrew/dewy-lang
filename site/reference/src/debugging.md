# Debugging

> **Language design.** [Generated coverage](/status/#ref-debugging) names measured programs and target restrictions; examples here illustrate the design.

## Current compiler and editor

Use `dewy build hello.dewy -g -o hello-debug`, then debug the executable with a native debugger. The VS Code extension uses CodeLLDB; configure `dewy.core.path` to the standalone `bin/dewy-core` or the checkout launcher. See [tools](/tools/) and the [extension guide](https://github.com/david-andrew/dewy-lang/blob/master/editors/vscode/README.md).

The following directive describes the language design. Its behavior is not certified by the command above; consult [generated coverage](/status/#ref-debugging).

## `$breakpoint`

`$breakpoint` is a statement (a metatag directive, like `$assert`; it takes nothing). When the program reaches it, it prints a banner naming the site and then every live binding of the enclosing function — its parameters and locals declared so far, innermost shadowing outer — one per line in the value's literal form (a string quoted, a container or object as its literal, a value that has no printable form as `name : type`):

```text
── breakpoint at t0.dewy:222 ──
  src = "# just a comment\n"
  i = 0
  matches = [[length=17 token_cls=LineComment]]
  longest_match_length = 17
```

At module level it shows the module's bindings. Functions, types, modules, ranges, and the compiler's hidden bindings are not shown.

Then the program stops. **Without a debugger** it waits at a `>>> ` prompt reading stdin. Commands start with a backslash, so that a plain expression stays free for evaluation later:

| input | effect |
|---|---|
| `\c` or an empty line | continue |
| `\q` | quit (exit status 130) |
| `\h` | list the commands |
| anything else | an expression — a compiled program cannot evaluate one yet, so it is refused with a note |

The end of input (a pipe that runs dry, `/dev/null`) continues, so a program with breakpoints left in still runs unattended.

**Under a debugger** (a native debugger attached to the process) the same directive traps into the debugger instead — the program stops on the `$breakpoint` line in your function, with the debugger's prompt and the snapshot already printed. The program decides at runtime by asking the kernel whether it is being traced, so one build serves both uses.
