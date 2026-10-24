# Contained paths, scoped by construction

Decided 2026-10-23 ([decisions](decisions.md): "Contained paths and untrusted input",
"Path guard", "Path validator name", "Soft preconditions", "Path safety, scoped by
construction", which replaces the source-trust design this file described before).
This is the design and the current implementation (`compiler/safe_paths.jo`,
`compiler/warn_if.jo`, `lib/std/files.jo`).

## The rule

Path traversal is a construction pattern, not a property of where text came from: the
program picks a base and joins text it has not proven to it (`p"{root}/{req.name}"`),
and the text climbs out (`../../etc/passwd`). So the compiler warns when unproven text
joined to a base reaches a file-system operation without `confine` or `contains` in
between. A path taken as it is, from arguments, the environment, input or anywhere
else, has no base to escape and does not warn. No value carries a trust brand, and no
library function is marked a source or a sink.

## The surface

- `Path` stays the everyday type and flows freely.
- `SafePath` is a `Path` with a brand meaning "does not escape its base". It is a
  `Path` everywhere: every `Path` method works on it, and it passes where a `Path`
  is wanted. Only the path library mints it. The compiler applies it to paths built
  from:
  - hardcoded text (`p"/srv/site/static"`, `p"{root}/index.html"`);
  - other `SafePath`s;
  - proven-safe components: one component, with no `/` (or `\`), not `.` or `..`,
    and not empty. Integers, floats and booleans always qualify (their text never
    holds a separator). So do text literals with that shape, string-literal unions
    whose members all have it, and single-assignment bindings of such values.

  A dynamic component must follow a separator. `p"{root}{n}"` is not a SafePath,
  because `/srv/data` and `-old` make `/srv/data-old`, which is a sibling.
- `root.contains(p)` returns `bool` and acts as a guard. In the true branch of
  `if root.contains(p) {...}`, `p` is a `SafePath`; after
  `if not root.contains(p) return ...`, it is a `SafePath` for the rest of the
  block. The guard also narrows through `and`.
- `root.confine(p)` returns `SafePath | PathEscape`. `PathEscape` is an `error`,
  so `root.confine(p) or_throw` is the expression form.
- A parameter, `let` or result declared `SafePath` takes only a proven path.
  Anything else is a compile error with the fix, `root.confine(p) or_throw`, or the
  guard. The editor applies the first.
- The file-system operations state the rule as a soft precondition:

  ```text
  @warn_if(path is not SafePath, "may escape its base")          # lib/std/files.jo
  exists = (path: Path) -> bool: ...
  @warn_if(p(path) is not SafePath, "may escape its base")       # the text forms
  read_text = (path: str) -> ...
  ```

  (`$warn_if path isnt? SafePath "may escape its base"` in Dewy.) A call from the
  program's own code warns, with the fix, when the path is not proven a `SafePath`
  and was built by the traversal pattern. The editor shows it as a squiggle and
  offers `root.confine(p) or_throw`. Hardcoded and whole paths never warn.

Containment is lexical. Both paths are split into parts (empty parts and `.`
dropped; on Windows `\` separates too). `p` must start with all of `root`'s parts,
and no later part may be `..` or a root (on Windows, no part may contain a drive
`:`). A `..` is refused even when it would come back down (`root/a/../b`), because
a symbolic link at `a` could take it elsewhere. A link inside the base can still
point outside. Closing that gap is `root.open_beneath(rel)` (below), not part of
this design.

## The traversal fact

A path's text, or text a path is made of, is a *traversal* when it is built by
interpolation (`p"{root}/{name}"`, `"{dir}/{name}"`) or string `+` from pieces in
which a piece of unproven text follows a base. A base is a `Path` piece, or any
content followed by a separator; a leading `/` alone is not one. Hardcoded text,
proven-safe components and `SafePath`s are proven pieces. Everything else is
unproven: text read at run time, a record's field, a parameter.

The fact then flows as a value does:

- through locals, `if` and `match` arms, conversions and `or_throw`;
- into and out of records, collections, fields and elements (a record built in
  place, or copied, keeps a fact per field);
- through library calls: the result holds what the arguments hold, and what the
  function values it is given return (`argv.map(x => p"{base}/{x}")`);
- through the program's own functions, by summary.

**Summaries.** Each function's result records the traversal it builds itself, the
parameters it returns (bits 0 to 30 of a mask) and the parameters whose text it joins
to a base (bits 31 to 61). At a call, the result holds what the returned arguments
hold, and it is a traversal where a joined argument is unproven. So
`path_for = (name:string) => p"{base}/{name}"` warns where
`path_for(argv[0]).exists` is called, and not for `path_for("index.html").exists`.
A parameter also records what callers give it: a traversal, or unproven text for a
joined parameter; a parameter passed on to another function's passes what it is
given along an edge, without walking the caller again. A file-system call inside a
helper reads these through the mask, so it warns when any caller gives it a
traversal or unproven text. A lambda's own
parameters are unproven, since its calls are not seen.

Globals keep one whole fact. Captured bindings are read through the variable they
capture, with the outer function's masks resolved to origins.

The warning names where the traversal was built: "built from unproven text on line
8", "built by `path_for` on line 12", or "unproven text given to `handle` on line
17" when a helper's parameter was joined.

## `$confine_external_paths`

The default treats a whole path as safe: it has no base to escape. That is a
convenience assumption ([assumptions](assumptions.md)), so it has an opt-out:
`$confine_external_paths` (provisional spelling) in a module, function or block makes
the file-system operations there ask every path to be proven a `SafePath`, the whole
ones included. The warning then reads "is not proven to stay inside a base, which
`$confine_external_paths` asks of every path a file-system operation gets", with the
same fixes. The acknowledgment for a path the program means to take as given is
`$confine_external_paths=false` around its use. `$bulletproof` includes it once the
bundle exists.

## Cost and demand

The pass runs after checking, over the checked trees of the program's own
functions. Library bodies are read only through signatures. It runs only on demand:

- the `SafePath` part runs when the program's own code names `SafePath`;
- the traversal part runs when the program's own code calls a function with a
  `SafePath` soft precondition (compiler/warn_if.jo notes it while checking).

A program with neither costs nothing beyond a flag test per call.

When it runs, each function body is walked once. A walk registers which facts it
reads: bindings, globals, results and parameters' incoming facts. When a fact grows,
its readers are walked again. Each fact only grows: its origin is set once, and its
mask gains bits up to the parameter count. So the work is
O(Σ body × (1 + facts that reach it)). In practice each body is walked once or
twice. All state is indexed maps keyed by local, global, field and function
instance. The `SafePath` checks and file-system calls are collected on the first
walk. Warnings are decided once, after the facts settle.

## Not in this design

- **`root.open_beneath(rel)`** opens with `openat2(RESOLVE_BENEATH)` or its
  equivalent, closing the symbolic-link gap.
- **Other joins.** `with_name`, `with_stem`, `with_suffix` and `join_path` given
  unproven text are not traversals yet; only interpolation and string `+` are.
- **Process, SQL and HTML.** The same shape (a soft precondition on the operation,
  a minted type that only the library's validator makes) fits them; none is built.
- **User-written validators and guards** need compile-time code, as for
  invariants.
- **`SafePath`-typed record fields and collection elements** are not checked yet.
  Only parameters, `let`s, assignments to such `let`s, and results are.
- **Precision.** Mutable parameters (`@x`) do not carry facts back to the caller.
  A function value called indirectly passes nothing to its parameters, except
  through library higher-order functions as above. Both under-approximate, so
  warnings are missed rather than invented.
