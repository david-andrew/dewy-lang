# 12. A child process and a temporary directory

`build` compiles into a scratch directory and copies the result out. `first_line` starts
`tail -f` to read one line, and leaves while the child still runs.

## (a) Implicit

```dewy
import p"@lib/std/files.dewy" as files
BuildFailed:type = type of error & [code:int]

build = (src:Path) => {
    let scratch = files.temp_dir() or_throw                              # removed, with its contents, when dropped
    let child = spawn(p"/usr/bin/cc" ["-o" "{scratch}/a.out" "{src}"]) or_throw
    let status = child.wait() or_throw                                   # consumes child
    if status not=? 0 return BuildFailed[status]                         # failure exit: scratch removed
    files.copy(p"{scratch}/a.out" p"out/a.out") or_throw;
}   # scratch removed here: a failed removal becomes build's result

first_line = (log:Path) => {
    let tail = spawn(p"/usr/bin/tail" ["-f" "{log}"]) or_throw
    let line = tail.stdout.read_line() or_throw
    line
}   # tail still runs: its $__abandon__ stops it; ProcessStopFailed becomes the result
```

## (b) Marked scope

```dewy
build = (src:Path) => {
    let scratch = files.temp_dir() or_throw
    let child = spawn(p"/usr/bin/cc" ["-o" "{scratch}/a.out" "{src}"]) or_throw
    let status = child.wait() or_throw
    if status not=? 0 return BuildFailed[status]
    files.copy(p"{scratch}/a.out" p"out/a.out") or_throw;
} or_throw

first_line = (log:Path) => {
    let tail = spawn(p"/usr/bin/tail" ["-f" "{log}"]) or_throw
    let line = tail.stdout.read_line() or_throw
    line
} or_throw      # acknowledges a failed stop; that tail is stopped at all stays implicit
```

## (c) Value-tied `defer`

```dewy
build = (src:Path) => {
    let scratch = files.temp_dir() or_throw
    defer scratch.remove() or_throw
    let child = spawn(p"/usr/bin/cc" ["-o" "{scratch}/a.out" "{src}"]) or_throw
    let status = child.wait() or_throw
    if status not=? 0 return BuildFailed[status]
    files.copy(p"{scratch}/a.out" p"out/a.out") or_throw;
}

first_line = (log:Path) => {
    let tail = spawn(p"/usr/bin/tail" ["-f" "{log}"]) or_throw
    defer tail.stop() or_throw
    tail.stdout.read_line() or_throw
}
```

## (d) Explicit close

```dewy
build = (src:Path) => {
    let scratch = files.temp_dir() or_throw
    let child = spawn(p"/usr/bin/cc" ["-o" "{scratch}/a.out" "{src}"]) or_throw
    let status = child.wait() or_throw
    if status not=? 0 return BuildFailed[status]
    files.copy(p"{scratch}/a.out" p"out/a.out") or_throw;
    scratch.remove() or_throw
}

first_line = (log:Path) => {
    let tail = spawn(p"/usr/bin/tail" ["-f" "{log}"]) or_throw
    let line = tail.stdout.read_line() or_throw
    tail.stop() or_throw
    line
}
```

## (e) Disposition on the binding

```dewy
build = (src:Path) => {
    let scratch drop or_throw = files.temp_dir() or_throw
    let child = spawn(p"/usr/bin/cc" ["-o" "{scratch}/a.out" "{src}"]) or_throw    # consumed by wait: no clause
    let status = child.wait() or_throw
    if status not=? 0 return BuildFailed[status]
    files.copy(p"{scratch}/a.out" p"out/a.out") or_throw;
}

first_line = (log:Path) => {
    let tail drop or_throw = spawn(p"/usr/bin/tail" ["-f" "{log}"]) or_throw
    tail.stdout.read_line() or_throw
}
```

## (f) Finish on success, clean up on failure

```dewy
build = (src:Path) => {
    let scratch = files.temp_dir() or_throw
    let child = spawn(p"/usr/bin/cc" ["-o" "{scratch}/a.out" "{src}"]) or_throw
    let status = child.wait() or_throw
    if status not=? 0 return BuildFailed[status]
    files.copy(p"{scratch}/a.out" p"out/a.out") or_throw;
}   # scratch is released: removing it can't fail (a leftover is reported in debug builds)

first_line = (log:Path) => {
    let tail = spawn(p"/usr/bin/tail" ["-f" "{log}"]) or_throw
    let line = tail.stdout.read_line() or_throw
    tail.stop() or_throw
    line
}
```

Without `tail.stop()`:

```text
error: tail (Child, line 2) is still running where first_line ends (line 4).
       Wait for it:  tail.wait() or_throw
       or stop it:   tail.stop() or_throw
```

`build` needs nothing: a child consumed by `wait` owes nothing, and the scratch directory's
removal is a release. Code that must know the directory is gone writes `scratch.remove() or_throw`.
A failed `cc` returns `BuildFailed`, a failure exit, which needs nothing either.

## Scores

| | Added over (a) | Hidden | Lossy | Forgotten |
|---|---|---|---|---|
| (a) | — | 2 | 0 | — |
| (b) | 2 tokens | 0 | 0 | warning; stopping `tail` stays implicit |
| (c) | 2 lines | 0 | 0 | warning |
| (d) | 2 lines | 0 | 0 | warning |
| (e) | 2 clauses | 0 | 0 | error; stopping `tail` stays implicit |
| (f) | 1 line | 0 | 0 | error that names the running child |
