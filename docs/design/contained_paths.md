# Contained paths and the untrusted-input brand

Decided 2026-10-23 ([decisions](decisions.md): "Contained paths and untrusted input",
"Path guard", "Path validator name"). This is the design and the current
implementation (`compiler/untrusted.jo`, `lib/std/files.jo`). It is the first user
of the untrusted-input brand sketched in
[safety and concurrency](safety_and_concurrency.md), built so later sinks reuse it.

## The surface

- `Path` stays the everyday type and flows freely.
- `SafePath` is a `Path` with a brand meaning "does not escape its base". It is a
  `Path` everywhere: every `Path` method works on it, and it passes where a `Path`
  is wanted. Only trusted validators mint the brand. The compiler applies it
  automatically to paths built from:
  - hardcoded text (`p"/srv/site/static"`, `p"{root}/index.html"`);
  - other `SafePath`s;
  - proven-safe components: one component, with no `/` (or `\`), not `.` or `..`,
    and not empty. Integers, floats and booleans always qualify (their text never
    holds a separator). So do text literals with that shape, string-literal unions
    whose members all have it, and single-assignment bindings of such values.

  A dynamic component must follow a separator. `p"{root}{n}"` is not a SafePath,
  because `/srv/data` and `-old` make `/srv/data-old`, which is a sibling.
  Hardcoded text is trusted wherever it sits.
- `root.contains(p)` returns `bool` and acts as a guard. In the true branch of
  `if root.contains(p) {...}`, `p` is a `SafePath`; after
  `if not root.contains(p) return ...`, it is a `SafePath` for the rest of the
  block. The guard also narrows through `and`.
- `root.confine(p)` returns `SafePath | PathEscape`. `PathEscape` is an `error`,
  so `root.confine(p) or_throw` is the expression form.
- A parameter, `let` or result declared `SafePath` takes only a proven path.
  Anything else is a compile error with the fix, `root.confine(p) or_throw`, or the
  guard. The editor applies the first.
- Untrusted is a tracked fact, not a kind of value. Text from outside the program
  carries the untrusted brand: command-line arguments, environment, standard input,
  file contents, the network and a child process's output. A path built from such
  text is a plain `Path` and passes through `Path` code freely. `UntrustedPath`
  names such a path in a signature. It is a plain `Path`, not an exception type.
- The safety net is a warning, which the editor also shows as a squiggle with the
  same fix. It fires when a path holding untrusted text reaches a file-system
  operation without being proven a `SafePath`. Hardcoded paths never warn.

Containment is lexical. Both paths are split into parts (empty parts and `.`
dropped; on Windows `\` separates too). `p` must start with all of `root`'s parts,
and no later part may be `..` or a root (on Windows, no part may contain a drive
`:`). A `..` is refused even when it would come back down (`root/a/../b`), because
a symbolic link at `a` could take it elsewhere. A link inside the base can still
point outside. Closing that gap is `root.open_beneath(rel)` (below), not part of
this design.

## The brand, in general

### Sources: marked where the input enters

A source API ends in the library primitive `__untrusted(x)`. It is the identity
function: no cost at run time, and inlined.

```text
args = () -> str[]: __untrusted(__os_args())                       # lib/core/os.jo
env = (name: str) -> str?: __untrusted(__os_env(name))
read_text = (path: Path) -> ...: __untrusted(__fsys_read_text(path.path))   # lib/std/files.jo
tcp_receive=(stream:TcpStream largest:int64=65536):>...=>__untrusted(__tcp_receive(stream largest))
```

The checker treats a call of a library function whose body is `__untrusted(...)`
as a source. A primitive, rather than an attribute, keeps the marking in the
library's own code, in either of its languages (Sloppy or Dewy). It also means an
older compiler building these sources sees an ordinary function.

The sources marked today are:

- `args` and `env`;
- `read_line`, `read_stdin` and `input`;
- an open `File`'s `read_line` and `read_bytes`;
- `read_text`, `read_bytes` and `read_at` (on paths and on text);
- `capture` (a child's output);
- `net.tcp_receive`.

A library that brings in outside text (an HTTP request parser, say) marks its
entry points the same way.

### Propagation

The brand rides on values whose type can hold arbitrary text: strings, byte
arrays, paths, and records, collections and unions that hold them. Numbers,
booleans and plain enums never carry it, because their text cannot inject
anything. So `to_int(arg)` is trusted, and so is `p"{base}/{n}.txt"`.

Through an expression, the brand follows:

- interpolation and every library call (`text.lower()`, `split`, `p(text)`, JSON
  decoding): the result holds what the arguments hold;
- constructors, collections, fields, elements, `if` and `match` arms, `or_throw`
  and the other conversions.

A function given untrusted text along with a function value (`xs.map(x => ...)`)
passes that text to the function's parameters.

Through the program's own code, the analysis is flow-insensitive per binding,
with two refinements:

- **Fields.** A record built in place, or copied from another binding, keeps a fact
  per field. So `Store[disk manifest]` taints `store.manifest` without tainting
  `store.disk`. A field assignment taints that field. An element assignment taints
  the whole collection.
- **Summaries.** Each function's result records the origin it adds itself and the
  parameters it returns (a mask). At a call, the result holds what the masked
  arguments hold. A helper like `path_for(name)` called with trusted text in one
  place and untrusted text in another warns only at the second call. A parameter
  also records what its callers pass it (its incoming origin). The callee's sinks
  read that through their masks, so a sink inside a helper warns when any caller
  gives it untrusted text.

Globals keep one whole fact. Captured bindings are read through the variable they
capture, with the outer function's masks resolved to origins.

### Validators remove the brand

A validator is a function whose declared result names `SafePath`, as
`confine = (root: Path, path: Path) -> SafePath | PathEscape` does. Its result is
trusted and branded. A guard is a library function marked `@guard(SafePath)`: its
true result proves its second argument (`contains`). A user function may also
return `SafePath`, and every value it returns is then held to the brand, so only
the library's validators mint it from untrusted input.

Values derived from a validated path are trusted. `(root.confine(f) or_throw).path`
is plain trusted text.

### Sinks

A sink is a library function marked `@sink(kind)`. For `path`, the first argument
and every other `Path` argument are what it opens. The file-system operations on
`Path` and their text forms are path sinks:

- reading, writing and appending;
- `exists`, `is_file`, `is_dir`, `list`, `walk`, `glob`, `size` and `modified`;
- making and removing files and directories;
- `copy_to`, `rename`, `replace`, `sync` and `chmod`.

The lexical methods (`name`, `parent`, `with_suffix`, ...) are not sinks.

Later sinks reuse every piece and only change the brand that clears them:

- process spawning: `@sink(process)` on `run`, `spawn` and `capture`'s program and
  arguments;
- SQL: `@sink(sql)` on query text, cleared by parameter binding;
- HTML: `@sink(html)` on markup, cleared by escaping.

Each later sink has its own validator and its own brand (`SafeSql`,
`SafeHtml`), minted the same way `SafePath` is.

## Cost and demand

The pass runs after checking, over the checked trees of the program's own
functions. Library bodies are read only through signatures, attributes and the
marker. It runs only on demand:

- the `SafePath` part runs when the program's own code names `SafePath`;
- the taint part runs when `__untrusted` and a sink were both instantiated.

A program with neither costs one integer compare per instantiated function and per
type name.

When it runs, each function body is walked once. A walk registers which facts it
reads: bindings, globals, results and parameters' incoming origins. When a fact
grows, its readers are walked again. Each fact only grows: its origin is set once,
and its mask gains bits up to the parameter count. So the work is
O(Σ body × (1 + facts that reach it)). In practice each body is walked once or
twice. All state is indexed maps keyed by local, global, field and function
instance. The `SafePath` checks and sink candidates are collected on the first
walk. Warnings are decided once, after the facts settle.

## Not in this design

- **`root.open_beneath(rel)`** opens with `openat2(RESOLVE_BENEATH)` or its
  equivalent, closing the symbolic-link gap.
- **Process, SQL and HTML sinks** reuse the machinery above.
- **User-written validators and guards** need compile-time code, as for
  invariants.
- **`SafePath`-typed record fields and collection elements** are not checked yet.
  Only parameters, `let`s, assignments to such `let`s, and results are.
- **Precision.** Mutable parameters (`@x`) do not carry facts back to the caller.
  A function value called indirectly passes nothing to its parameters, except
  through library higher-order functions as above. Both under-approximate, so
  warnings are missed rather than invented.
