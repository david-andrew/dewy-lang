# Command-Line Programs, Files, and Processes

> [Generated coverage](/status/#ref-command-line-programs) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

This page covers what a program uses to talk to the system it runs on: its arguments and exit status, the standard streams, the environment, files, child processes, secrets and sockets.

## `main` and Arguments

`main` is optional: without it, a file runs top to bottom as a script. With it, the top-level statements run first, then `main` runs once. Only the entry file's `main` runs.

`main` takes no parameters, or the command line as `main = (argv:array<string>) => ...`. `args` gives the same array anywhere in the program. The first element is the program as it was started.

<!-- dewy-example: {"mode":"run","args":["red","green"],"stdout":"2 arguments: [\"red\" \"green\"]\n"} -->
```dewy
main = (argv:array<string>) => {
    let words = argv[$clamp 1..]      # everything after the program
    printl"{words.length} arguments: {words}"
}
```

## Exit Status

`main` returns `void` or the errors that reach it, an ordinary `void | E` result, declared or inferred. It gives no exit code: success exits 0.

- An error reaching `main` is printed on standard error as its kind and its `message` field, if it has one: `error: UsageError: usage: fetch HOST`. The rest of the payload may hold secrets, so only a debug build (`-g`) prints the whole value.
- The exit code is the error kind's: 1, 2, 3, … in the order the kinds are declared (or as a declared result lists them), up to 100. 101 is a failed runtime check.
- An error type with an `exit_code` field pins its own code, from 1 to 100. An error can never report success.
- `exit(n)` ends the program with code `n`, a `uint8`. A constant outside 0–255 is a compile error; a computed code is an obligation (`exit(min(failures.length 255))` proves it).
- `dewy build --exit-codes file.dewy` prints the table without building.

<!-- dewy-example: {"mode":"run","args":["nowhere"],"exit":69,"stdout":""} -->
```dewy
UsageError:type = type of error & [message:string]
Offline:type = type of error & [exit_code:int64=69]

connect = (host:string):>void | Offline => {
    if host =? "nowhere" return Offline[]
    printl"connected to {host}"
}

main = ():>void | UsageError | Offline => {
    let argv = args
    if argv.length <? 2 return UsageError["usage: fetch HOST"]
    connect(argv[1]) or_throw
}
```

Without arguments this prints `error: UsageError: usage: fetch HOST` on standard error and exits 1; `fetch nowhere` exits 69. The table for it:

```text
0 success
1 UsageError
69 Offline (its exit_code)
101 a panic
```

## Parsing Arguments: `argparse`

`import argparse` reads `argv` into a typed record. The spec is a record type whose fields are descriptors, each holding an argument's type, default, short name and help:

| Descriptor | Written | Result field |
|---|---|---|
| `argparse.Positional<T>(...)` | a bare word, in field order | `T` |
| `argparse.Named<T>(...)` | `name=value`, `--name=value`, or `-s=value` with a short | `T` |
| `argparse.Flag(...)` | `--name`, `-n`, or `name=true` / `name=false` | `bool` |

Each descriptor takes `help=`, `default=` and `short=`. `argparse.parse(Spec argv about="..." version="...")` gives the record.

<!-- dewy-example: {"mode":"run","args":["example.org","-r=5","timeout=90s","header=A:1","header=B:2","-v"],"stdout":"example.org retries=5 timeout=90s format=text headers=[\"A:1\" \"B:2\"] verbose=true\n"} -->
```dewy
import argparse

Args:type = [
    url = argparse.Positional<string>(help="what to fetch")
    retries = argparse.Named<int64<n => 0 <=? n and n <=? 9>>(default=3 short='r' help="tries after the first")
    timeout = argparse.Named<Duration>(default=30s help="give up after this long")
    format = argparse.Named<'text' | 'json'>(default='text' help="how to print")
    header = argparse.Named<array<string>>(help="extra headers")
    verbose = argparse.Flag(help="say more")
]

main = (argv:array<string>) => {
    let a = argparse.parse(Args argv about="fetch a page")
    printl"{a.url} retries={a.retries} timeout={a.timeout} format={a.format} headers={a.header} verbose={a.verbose}"
}
```

The command line fills the spec as a constructor call fills a record:

- Bare words fill the `Positional` fields in field order. `name=value` fills any field by name, positionals included. Defaults fill the rest.
- `--ignore-case` names the field `ignore_case`.
- A valued argument's short is written `-r=5`, never `-r 5`. `--retries 2` is an error that says to write `retries=2`.
- A flag's short is its first letter, unless another flag without a `short=` of its own starts with it. `short='x'` chooses one and `short=none` gives none. Flag shorts combine: `-in` is `-i -n`.
- `argparse.Flag(default=true)` is on unless `--no-name`, `name=false` or its short turns it off.
- `--` ends the options; the words after it are positionals.
- `array<T>` repeats (`header=a header=b`) and defaults to empty; a positional array takes the remaining words. `T?` defaults to `none`. Any other argument without a default is required.
- Each value is read by its type's text reader, `T(text)`: numbers, `bool`, `Path`, `Duration` (`90s`, `1.5hour`, `250ms`), literal unions and refined integers. A value out of range is a usage error (`retries=10: must be from 0 to 9`), and the field keeps its refinement.
- A misspelled name is answered with the nearest one: `unknown flag --froce (did you mean --force?)`.

### Usage Errors, `--help` and `--version`

`argparse.parse` prints a usage error and the usage on standard error and exits with code 2:

<!-- dewy-example: {"mode":"run","args":["example.org","retries=10"],"exit":2,"stdout":""} -->
```dewy
import argparse

Args:type = [
    url = argparse.Positional<string>(help="what to fetch")
    retries = argparse.Named<int64<n => 0 <=? n and n <=? 9>>(default=3 short='r' help="tries after the first")
]

main = (argv:array<string>) => {
    let a = argparse.parse(Args argv)
    printl"{a.url} {a.retries}"
}
```

```text
fetch: retries=10: must be from 0 to 9
usage: fetch [options] URL

  url                   string            what to fetch
  -r=, retries=         int64, 0 to 9     tries after the first (default 3)
  -h, --help                              show this help
```

`--help` (`-h`) prints the usage on standard output and exits 0. With `version="1.4.0"`, `--version` prints the program's name and version and exits 0. The usage has a line per field: how it is written, its type spelled in Dewy (a refined integer as its base and range), its help and its default.

`argparse.try` gives the record or an `argparse.UsageError` instead of exiting. The error has a `message` and the rendered `help`; for `--help` and `--version` the message is empty.

<!-- dewy-example: {"mode":"run","stdout":"copy a.txt to b.txt, force=true\ncopy a.txt to b.txt, force=false\nusage error: unknown flag --froce (did you mean --force?)\nusage error: dest is required\n"} -->
```dewy
import argparse

Args:type = [
    source = argparse.Positional<Path>(help="file to copy")
    dest = argparse.Positional<Path>(help="where to put it")
    force = argparse.Flag(help="replace an existing file")
]

show = (argv:array<string>) => {
    let a = argparse.try(Args argv about="copy a file")
    if a is? argparse.UsageError {
        printl"usage error: {a.message}"
        return
    }
    printl"copy {a.source} to {a.dest}, force={a.force}"
}

main = () => {
    show(["cp" "a.txt" "b.txt" "-f"])
    show(["cp" "dest=b.txt" "a.txt"])
    show(["cp" "a.txt" "--froce"])
    show(["cp" "a.txt"])
}
```

Declare the spec as a type to keep its written order. An anonymous record's fields are in name order, so an anonymous spec with two or more positionals is a compile error:

<!-- dewy-example: {"mode":"reject","diagnostic":"an anonymous spec's positional fields fill in name order, not as written"} -->
```dewy
import argparse

main = (argv:array<string>) => {
    let spec = [source = argparse.Positional<string>() dest = argparse.Positional<string>()]
    let a = argparse.parse(spec argv)
    printl"{a.source} -> {a.dest}"
}
```

`argparse` is ordinary Dewy over `fields(S)`, `$field`, overloads on the descriptor types and `T(text)`. Subcommands, environment-variable fallbacks and rules across several arguments are not built yet.

## Standard Streams

`printl(x)` writes a value and a line break; `print(x)` writes it without one. `file=stderr` writes to standard error instead; `stdout` and `stderr` are in the prelude.

<!-- dewy-example: {"mode":"run","stdout":"loaded 3 files\ndone\n"} -->
```dewy
console.info("loaded {3} files")
console.warn("cache is stale")
printl("plain text on standard error" file=stderr)
console.debug("only in debug builds")
printl"done"
```

- `console.info` writes as `printl` does. `console.warn` and `console.error` write to standard error, yellow and red on a terminal. `console.debug` writes to standard error and is left out of release builds, its arguments unevaluated.
- Colour is used only when the stream is a terminal. `NO_COLOR` turns it off; `FORCE_COLOR` or `CLICOLOR_FORCE` turns it on. `console.color = 'always'`, `'never'` or `'auto'` overrides both.
- A failed write to standard output ends the program with `error: could not write standard output` and exit 1. Output to a closed pipe (`| head`) ends it quietly.

### Reading Input

| Call | Gives |
|---|---|
| `read_line` | the next line without its line break: `string \| Canceled \| FileError \| none` (`none` at the end) |
| `read_stdin()` | all of standard input: `string \| FileError \| Canceled` |
| `input(prompt)` | shows the prompt, reads a line: `string \| InputFailure` |
| `input_int(prompt)`, `input_float(prompt)` | asks again until a number comes: `int64` or `float64` `\| InputFailure` |

`InputFailure` is `EndOfInput | FileError | Canceled`. An unhandled `EndOfInput` reaching `main` is reported as `error: EndOfInput`, exit 1.

<!-- dewy-example: {"mode":"check"} -->
```dewy
main = () => {
    let count = 0
    loop true {
        let line = read_line
        if line is? exception break       # end of input, a read error or cancellation
        count += line.length
    }
    printl"{count} characters"
    let level = input_int("level? ") ?? 1
    printl"level {level}"
}
```

With no file, `dewy` reads the whole program from standard input when it is piped: `echo 'printl"hi"' | dewy`.

## Environment

`env(name)` gives a variable's value, or `none` when it is not set.

<!-- dewy-example: {"mode":"run","stdout":"port 8080\n"} -->
```dewy
let address = env("DEWY_EXAMPLE_HOST") ?? "localhost"
let port = to_int(env("DEWY_EXAMPLE_PORT") ?? "8080") ?? 8080
printl"port {port}"
```

Settings that change how a program compiles are written in the source, never read from the environment (see [Settings and Safety Levels](settings.md)).

## Paths

`p"dir/file.txt"` is a path literal and `p(text)` builds a path at run time. Both make a `Path`, which holds its text in `.path`. A path interpolates as its text, so paths are joined by interpolation: `p"{root}/{name}.csv"`. There is no `join` method.

The lexical methods read only the text and follow Python's `pathlib`:

<!-- dewy-example: {"mode":"run","stdout":"main.dewy main .dewy\nproject/src src\n[\"project\" \"src\" \"main.dewy\"]\nproject/src/main.md\n"} -->
```dewy
let src = p"project/src/main.dewy"
printl"{src.name} {src.stem} {src.suffix}"
printl"{src.parent} {src.parent.name}"
printl(src.parts)
printl(src.with_suffix(".md"))
```

`name`, `stem`, `suffix` (with its dot; `.bashrc` has none), `parent`, `parts` (a leading `/` is the root part), `is_absolute`, `with_name`, `with_stem` and `with_suffix`. On Windows `\` also separates parts, and a drive or share root is the root part; paths the methods make use `/`.

## Files

The file-system methods give every outcome as a value:

| Method | Gives |
|---|---|
| `exists`, `is_file`, `is_dir` | `bool` |
| `read_text` | `string` (or also `InvalidUtf8`) |
| `read_bytes` | `array<uint8>` |
| `write_text(text)`, `write_bytes(bytes)` | the byte count |
| `list` | the directory's entry names |
| `walk` | every file under a directory, sorted |
| `glob"*.dewy"` | sorted paths under it matching a pattern (`*`, `?`, `**`) |
| `size` | the byte count |
| `modified` | the `Instant` it last changed (provisional) |
| `copy_to(target)` | the byte count |
| `mkdir`, `make_dirs`, `rmdir`, `unlink`, `rename(target)`, `chmod(0o644)` | `true` |

A failure is `FileNotFound`, `FileAccessDenied`, `IsDirectory`, `FileExists` or `FileError` (any other failure). All are `error`s. `FileError` is their sibling, not their parent, so list the kinds you forward or leave the result type to be inferred. The operations are also cancellation points, so their results include `Canceled` (see [Concurrency](concurrency.md#canceled)).

<!-- dewy-example: {"mode":"run","fixtures":{"notes.txt":"alpha\nbeta\n"},"stdout":"alpha\nbeta\nwrote 9 bytes; size 9\n[\"report.txt\"]\nFileNotFound\nfalse\n"} -->
```dewy
main = () => {
    match p"notes.txt".read_text {
        text:string => print(text)
        <FileNotFound> => printl"no notes"
        _ => printl"cannot read the notes"
    }
    let out = p"out/report.txt"
    out.parent.make_dirs or_throw;
    let n = out.write_text("total 42\n") or_throw
    printl"wrote {n} bytes; size {out.size or_throw}"
    printl(p"out".list or_throw)
    printl(p"missing.txt".read_text)
    out.unlink or_throw;
    p"out".rmdir or_throw;
    printl(p"out".exists)
}
```

`write_text` and `write_bytes` replace a file atomically: the new contents go to a file beside it, reach the disk, and are renamed over it, so a reader or a crash sees the old file or the new one. Its permissions are kept. A symbolic link there is refused, not followed.

The same operations exist as functions of a path's text: `read_text(path)`, `write_text(path text)`, `file_exists`, `list_directory`, `make_directory`, `remove_file` and others. `append_file(path text)` adds to the end of a file, making it if it is missing.

In a web build, files live in the page's memory (see [Targets](targets.md#what-differs-on-the-web)).

### Contained Paths

A `SafePath` is a `Path` proven not to escape its base. It passes wherever a `Path` is wanted. A path is a `SafePath` when it is built from hardcoded text, other `SafePath`s, and components proven safe: one component with no `/`, not `.` or `..`, and not empty (integers, booleans and literal unions of such names, for example). A component must follow a `/`.

A path that joins unproven text to a base is a plain `Path`. `root.confine(p)` gives it as a `SafePath`, or `PathEscape` when it leaves `root`. `root.contains(p)` is the same test as a `bool`, and narrows `p` to a `SafePath` in its true branch.

<!-- dewy-example: {"mode":"run","stdout":"inside: site/docs/b.dewy\nfalse\n"} -->
```dewy
main = () => {
    let root = p"site"
    let name = "docs/b.dewy"
    match root.confine(p"{root}/{name}") {
        safe:SafePath => printl"inside: {safe}"
        <PathEscape> => printl"escapes"
    }
    printl(root.contains(p"{root}/../secret"))
}
```

Passing an unproven path where a `SafePath` is declared is an error that names both fixes:

<!-- dewy-example: {"mode":"reject","diagnostic":"is not proven to stay inside its base"} -->
```dewy
serve = (f:SafePath) => printl(f)
main = (argv:array<string>) => {
    let root = p"static"
    serve(p"{root}/{argv[1]}")
}
```

A file operation on such a path is a warning (`may escape its base`). A hardcoded path never warns, nor does a path taken whole, as `p(env("HOME") ?? "/")`: it has no base to escape. `$confine_external_paths` (provisional spelling) in a module, function or block requires every path a file operation gets there to be proven a `SafePath`.

The test reads the text alone: `p` must start with `root`'s parts, and no later part may be `..` or a root. A symbolic link inside `root` that points outside is not detected yet.

## Processes

| Call | Gives |
|---|---|
| `run(program args)` | the exit status; the child shares the standard streams |
| `run_silent(program args)` | the exit status; the child's output is discarded |
| `capture(program args)` | an `Output`: `status`, `stdout` and `stderr` bytes, `stdout_text` and `stderr_text` (`string \| none`) |
| `spawn(program args)` | a `Child`, whose `wait` gives the exit status |

`program` is a path: there is no `PATH` search (`run("/usr/bin/env" ["python3" "tool.py"])` does one). The status is the exit code, or `128 + n` when signal `n` ended the child. `SpawnError` means no child could be started; a program that cannot be run ends with 127, as in a shell. `capture` drains each stream as it fills, up to 64 MiB; more ends the child with a `FileError`.

<!-- dewy-example: {"mode":"run","stdout":"from the child\nstatus 3\n0 captured words\nquiet 0\nwaited 5\n127\n"} -->
```dewy
main = () => {
    let status = run("/bin/sh" ["-c" "echo from the child; exit 3"])
    printl"status {status}"
    let out = capture("/bin/echo" ["captured" "words"]) or_throw
    print"{out.status} {out.stdout_text ?? ""}"
    printl"quiet {run_silent("/bin/sh" ["-c" "echo hidden"])}"
    let child = spawn("/bin/sh" ["-c" "exit 5"]) or_throw
    printl"waited {child.wait}"
    printl(run("/no/such/program" []))
}
```

Process waits are cancellation points; owned process helpers cancel and reap their child. On Windows, `run` works, and `run_silent`, `spawn` and `capture` give `SpawnError` for now. A `.bat` or `.cmd` program is refused, since cmd.exe would read its arguments again as commands. In a web build every process call is `SpawnError`.

## Secrets

A `secret<T>` holds a `T` that no output shows. `secret(x)` makes one, and a `T` goes by itself wherever a `secret<T>` is declared. `s.reveal` gives the value back; it is the only way out.

<!-- dewy-example: {"mode":"run","stdout":"[user=\"ann\" pass=<redacted>]\npassword: <redacted>\nfalse\n7\n"} -->
```dewy
Login:type = [user:string pass:secret<string>]
check = (pw:secret<string> attempt:string):>bool => pw =? attempt
main = () => {
    let login = Login["ann" "hunter2"]
    printl(login)
    printl"password: {login.pass}"
    printl(check(login.pass "guess"))
    printl(login.pass.reveal.length)
}
```

- Wherever its value would become text, a secret is written `<redacted>`: printing, interpolation, records and containers holding one, errors reaching `main` (even in a debug build), editor hovers and debuggers.
- JSON has no writer for a secret; writing one is a compile error. `from_json` reads a `secret<T>` field as a `T`.
- `write_text` and `write_bytes` given a secret create a file only its owner can read (`0o600`; an owner-only access list on Windows).
- Equality (`=?`, `not=?`) gives a plain `bool`, revealing one bit, and compares strings and integer arrays in constant time. Ordering gives `secret<bool>`. Arithmetic gives a secret of the result.
- A secret costs nothing: it is stored and passed exactly as its `T`.

Using a secret as its `T`, or reaching its members, is a compile error that names `.reveal`:

<!-- dewy-example: {"mode":"reject","diagnostic":"a secret<string> has no member 'length': its value is hidden"} -->
```dewy
let s = secret("abc")
printl(s.length)
```

## Networking

`import net` gives blocking TCP sockets. Each call gives a `net.NetError` (an `error` with a `message`) when the system refuses, or `Canceled` when its task is canceled.

<!-- dewy-example: {"mode":"check"} -->
```dewy
import net
main = ():>void | net.NetError | Canceled => {
    let server = net.tcp_listen(0) or_throw           # 0: a free port, on loopback
    let client = net.tcp_connect("127.0.0.1" server.port) or_throw
    let peer = net.tcp_accept(server) or_throw
    net.tcp_send(client "hello") or_throw
    let got = net.tcp_receive(peer)
    if got is? none return                           # the client closed
    printl((got or_throw) as string | none)
    loop stream in [client peer] net.tcp_close(stream)
    net.tcp_close(server)
}
```

| Call | Does |
|---|---|
| `tcp_listen(port host="127.0.0.1" backlog=128)` | gives a `TcpListener`; its `port` is the one bound (the system's choice for 0) |
| `tcp_accept(listener)` | waits for the next connection, a `TcpStream` |
| `tcp_connect(host port)` | connects to a numeric address or `localhost` |
| `tcp_send(stream data)` | sends all of a string or `array<uint8>` |
| `tcp_receive(stream largest=65536)` | waits for some bytes; `none` once the other side has closed |
| `tcp_close(x)` | closes a stream or a listener |

The default host admits only this machine. Native targets use the system's C library (Winsock on Windows). A web page has no TCP sockets; the game library's WebSocket messages (`net.listen`, `net.connect`, `net.send`, `net.receive`) come with the same import and work in browsers too.
