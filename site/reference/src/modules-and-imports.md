# Modules and Imports

Each source file defines a module containing its top-level bindings and executable initialization expressions.

## Relative Source Imports

An import path resolves relative to the file containing the import:

```dewy
from p"lib.dewy" import (answer add)
import p"lib.dewy" as library
```

Selective imports bind the requested names directly. `as` renames a selected binding. A namespace import retains qualification. Importing a path without a selection splats its top-level bindings into the current scope.

The `from path import names` and `import names from path` orders are equivalent.

## Import Sources

`p` is an ordinary prelude function producing a structural path value. Any exact compile-time object with the required string `path` field satisfies the source-import contract:

```dewy
from [path="lib.dewy"] import answer
```

Source imports must be known while constructing the module graph. Runtime strings cannot select source modules.

## Binding Kinds

Values, constants, functions, overload sets, and type aliases are importable. Imported type values remain compile-time values in the receiving module.

## Graph and Initialization

Reachable source modules share a coherent type environment, initialize once in dependency order, and reject unresolved names, cycles, and collisions. A source suffix is conventional and does not select different Dewy semantics.

## Targets

`$target` is a compile-time string naming the backend (`x86_64`, `riscv`, `arm`, `c`, `wasm32`). Comparing `$target` with a string literal (`=?`, `not =?`, `in?` and `not in?` against a literal list, combined with `not`, `and`, `or`) folds during checking; an `if` whose condition is such a comparison skips its dead arms without checking them — they may import files that exist only for other targets — and splices the live arm's `{}` body into the enclosing scope so gated imports and declarations bind there. Plain literal conditions keep ordinary flow semantics.

`$supported_targets = ["x86_64" ...]` lists the backends a module accepts; compiling for another target is an error.

## Prelude

Before checking an ordinary module, the compiler supplies a source prelude of shadowable bindings: paths, printing, `rational` and `fixed` numbers, units, and the current target's services layer. `$no_prelude = true` disables those implicit bindings for its containing module only. Imported modules retain their own prelude decision.

## Provisional Package Facilities

Installed package lookup, directory or glob imports, non-source artifacts, project-wide freestanding policy, and domain-library naming remain provisional. They must extend rather than contradict file-relative module identity and one-time initialization.

## Paths

`p"…"` is a path literal and `p(text)` builds a path at runtime; both are the prelude's `Path`, a value holding its text (`.path`). A path interpolates as its text (`Path` declares the conversion method `__as__ = ():>string => path`, so `path as string` is the text too), so `p"{root}/{name}"` is how paths are joined — there is no `join` method, since interpolation is strictly more flexible. The methods follow Python's `pathlib`:

- lexical: `name`, `stem`, `suffix` (with its dot; a dotfile has none), `parent`, `parts` (a leading `/` is the root part), `is_absolute`, `with_name(name)`, `with_stem(stem)`, `with_suffix(suffix)`;
- the file system, every outcome a value: `exists`, `is_file`, `is_dir`, `list` (the directory's entries), `read_text` (`string | FileNotFound | FileAccessDenied | IsDirectory | FileExists | FileError | InvalidUtf8`), `read_bytes`, `write_text(text)` and `write_bytes(bytes)` (the byte count or an error), `mkdir`, `rmdir`, `unlink` (`true` or an error). Zero-argument methods are read like fields: `source.parent.name`.

```dewy
let source = p"{project}/src/main.dewy"
match source.read_text {
    text:string     => compile(text)
    <FileNotFound>  => report"no such file: {source}"
    _               => report"cannot read {source}"
}
let out = source.with_suffix(".udewy")
```

The same operations exist as free functions on a path's text (`read_text(path:string)`, `write_text`, `file_exists`, `is_file`, `is_directory`, `make_directory`, `remove_directory`, `remove_file`), provided by the target's file-system module (`library/linux/files.dewy`).

## Processes

The prelude runs programs as child processes (`library/linux/process.dewy`); every outcome is a value. `program` is a path — the kernel does no `PATH` search, so `run("/usr/bin/env" ["python3" …])` is how to get one — and `args` are the arguments after it. A child inherits the environment, and a failed exec reports `127` like a shell would. A status is the exit code, or `128 + n` when signal `n` ended the child; `SpawnError` means the child could not be started.

- `run(program args):>int64 | SpawnError` waits for the status; the child shares the standard streams. `run_silent` sends its stdout and stderr to `/dev/null`.
- `spawn(program args):>Child | SpawnError` starts the child and returns it; `child.wait` yields the status. Several children may run at once.
- `capture(program args):>Output | SpawnError` waits with the child's output collected: `status`, `stdout` and `stderr` (bytes, drained as the pipes fill, so a large output cannot block the child), and `stdout_text` / `stderr_text` (`string | undefined`: the bytes decoded, `undefined` when they are not UTF-8).
- `environment(name):>string | undefined` reads one of this process's own environment variables.

<!-- dewy-example: compiler -->

```dewy
let main = ():>int64 => {
    match capture("/bin/sh" ["-c" "echo out; echo err 1>&2; exit 3"]) {
        result:Output => {
            match result.stdout_text { text:string => printl"{text}"  <undefined> => {} }
            return result.status                       # 3
        }
        <SpawnError> => return 1
    }
}
```

Still ahead: a working directory and a custom environment for the child, and reading a child's output as it runs.
