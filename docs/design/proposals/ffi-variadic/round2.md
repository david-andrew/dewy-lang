# Variadic C functions (D51): round 2, dogfood

Round 1 picked `...args` (no type) to end an `$extern` declaration's parameters. This round
writes fourteen small programs with it, using only spellings that exist today or that D51
proposes, and grades each 1-5 on obvious, discoverable, concise, safe by default and complete.
Each program is compared with Python (ctypes, cffi), Go (cgo), Rust (`extern "C"` with `...`),
TypeScript (Deno and Bun FFI) and Swift (`CVarArg`, `withVaList`). Nothing here is implemented.

Grading. **Safe** means the mistakes this program invites are caught when compiling, or are
confined to one place a reader can see; a call being `$unsafe` does not by itself earn a 5.
Where a low grade comes from Dewy's FFI in general rather than from D51, the reason says
"(FFI)"; those gaps are listed at the end and are out of D51's scope.

## How the others do it

| | Declares a variadic C function | Extras' C types | Narrow ints, `float`, `bool` | Format checked |
|---|---|---|---|---|
| Python ctypes | no split between fixed and extra; any call shape | guessed from the value; floats need `c_double(x)` | not promoted; the program wraps | no |
| Python cffi | `ffi.cdef("int printf(const char *, ...);")` | each extra must be typed cdata: `ffi.cast("int", n)` | the program casts | no |
| Go cgo | cannot call one; a C wrapper in the preamble per call shape | | | the C compiler, in the wrapper |
| Rust | `fn printf(f: *const c_char, ...) -> c_int;` | from the value; unsuffixed literals are `i32` | an error (E0617) with "cast to `c_double`/`c_int`" | no |
| Deno, Bun | no variadic form: one fixed signature per shape, the declaration D51 calls undefined | | | no |
| Swift | not imported; call the `v` variant with `withVaList([...])` | `CVarArg`; `Int` crosses as 64 bits, so `%d` is a classic bug | `Float` is promoted | no |
| Dewy, D51 | `printf = (format:string ...args):>int32` | from the value | promoted, as C does | no |

## Round 0: D51 as written

### 1. printf: a report in a C tool's exact layout

```dewy
# Keep the column layout of the C tool this replaces, so diffs of its output stay empty.
$extern
printf = (format:string ...args):>int32
$extern
fflush = (stream:ptr<uint8>?):>int32

Part:type = [sku:string count:int32 price:float64]

main = () => {
    let parts = [Part["bolt-m6" 1200 0.04] Part["nut-m6" 950 0.02] Part["washer" 4000 0.01]]
    $unsafe {
        printf("%-10s %6s %9s\n" "sku" "count" "price");
        loop p in parts { printf("%-10s %6d %9.2f\n" p.sku p.count p.price); }
        printf("%d parts\n" int32(parts.length));
        fflush(none);   # C's stdout buffer is not Dewy's: flush before printl or exit
    }
}
```

| Obvious | Discoverable | Concise | Safe | Complete |
|---|---|---|---|---|
| 5 | 3 | 4 | 2 | 4 |

- Discoverable 3: `printf("%d parts\n" parts.length)` is an error (`length` is `int`), and D51 says
  nothing about what the message suggests. Worse, D51's own example passes the literal `3`, which
  is an `int` too: as written, the example does not compile.
- Safe 2: the format is not checked against the extras; `%d` given a `float64` is undefined.
- Complete 4: C's stdout buffer and `printl`'s are separate, so output interleaves out of order
  unless the program flushes; whether C's buffer is flushed at exit at all needs checking, since
  the C library is loaded on first call rather than started (FFI).
- Compared: Rust reads the same and also needs `unsafe`; cffi needs a cast per extra; Go needs a
  C wrapper; Swift has no `printf` and its `Int` breaks `%d`.

### 2. snprintf: format into a buffer, keep the result as a Dewy string

```dewy
# Format sizes as the C tool did ("1.5 KiB") and keep them as Dewy strings.
$extern
snprintf = (buf:ptr<uint8> size:uint64 format:string ...args):>int32

c_format = (format:string value:float64 unit:string):>string => $unsafe {
    let buf:array<uint8> = [loop _ in [0..32) uint8(0)]
    let n = snprintf(buf.ptr uint64(buf.length) format value unit)
    if n <? 0 return "?"                     # an encoding error
    if n >=? buf.length {                    # truncated: C reports the length it wanted
        buf = [loop _ in [0..n + 1) uint8(0)]
        snprintf(buf.ptr uint64(buf.length) format value unit);
    }
    buf[$clamp 0..n) as string | none ?? "?"
}

human = (size:int64):>string => {
    if size <? 1024 return "{size} B"
    if size <? 1024 * 1024 return c_format("%.1f %s" float64(size) / 1024.0 "KiB")
    c_format("%.1f %s" float64(size) / (1024.0 * 1024.0) "MiB")
}

main = () => loop size in [512 1536 52428800] { printl(human(size)) }
```

| Obvious | Discoverable | Concise | Safe | Complete |
|---|---|---|---|---|
| 4 | 3 | 3 | 3 | 5 |

- The result is `int32`, as C's: negative on an encoding error, and possibly `>= size` when
  truncated. Declaring it `int32<(>=? 0)>` would be a false claim (glibc returns -1 for a bad
  multibyte sequence), so the plain type is right and the program checks.
- Discoverable 3, concise 3: the zero-filled buffer and `buf[$clamp 0..n) as string | none ?? "?"`
  are not things a newcomer finds (FFI). The two-call pattern is C's own.
- Safe 3: the buffer and its size are passed separately, as in every language here.
- Compared: Rust and ctypes write the same two-call dance; Swift uses `String(format:)` instead.

### 3. ioctl: terminal width for a progress bar

```dewy
# Size a progress bar to the terminal: ioctl(TIOCGWINSZ) fills a winsize.
WinSize:type = [rows:uint16 cols:uint16 x_pixels:uint16 y_pixels:uint16]
$extern
ioctl = (fd:int32 request:uint64 ...args):>int32
const TIOCGWINSZ:uint64 = 0x5413   # Linux; macOS is 0x40087468

columns = ():>int64 => $unsafe {
    let ws:array<WinSize> = [WinSize[0 0 0 0]]
    if ioctl(1 TIOCGWINSZ ws.ptr) not=? 0 or ws[0].cols =? 0 return 80
    int64(ws[0].cols)
}

bar = (done:int64 total:int64):>string => {
    let inner = max(columns() - 2 10)
    let filled = done * inner // max(total 1)
    "[{[loop _ in [0..filled) "#"].join("")}{[loop _ in [filled..inner) " "].join("")}]"
}

main = () => loop step in [0 25 50 100] { printl(bar(step 100)) }
```

| Obvious | Discoverable | Concise | Safe | Complete |
|---|---|---|---|---|
| 5 | 4 | 5 | 3 | 5 |

- Discoverable 4: request numbers differ by platform and come from headers (FFI).
- Safe 3: the request decides what the third argument must be; nothing ties `TIOCGWINSZ` to
  `ptr<WinSize>`. Today a program would write `ioctl = (fd request out:ptr<WinSize>)`, which ties
  them but is the fixed declaration D51 calls undefined.
- Compared: Rust and ctypes are the same; Go needs a wrapper (or `x/sys/unix.IoctlGetWinsize`).

### 4. execl: hand the process to a shell

```dewy
# A launcher that replaces itself with a shell command; it returns only on failure.
$extern
execl = (path:string arg0:string ...args):>int32
$extern(name='__errno_location')
errno_at = ():>ptr<int32>

main = () => {
    let command = "exec printenv HOME"
    $unsafe execl("/bin/sh" "sh" "-c" command none);
    printl"exec failed: errno {$unsafe errno_at()[0]}"
    exit(127)
}
```

| Obvious | Discoverable | Concise | Safe | Complete |
|---|---|---|---|---|
| 4 | 3 | 5 | 1 | 4 |

- D51 does not say how `none` crosses as an extra. It has no pointer type of its own, so as written
  the sentinel cannot be passed at all (complete 4, discoverable 3).
- Safe 1: leaving out `none` compiles and C reads past the arguments. This is inherent to
  `execl`'s C contract: no rule on untyped extras can see it.
- Errno is reached through a Linux-only name (FFI).
- Compared: Rust (`ptr::null::<c_char>()`), ctypes (`None`) and cffi (`ffi.NULL`) carry the same
  hazard; Go and Swift steer to `execv`/`posix_spawn` with an array, which is the safe route here
  too: `run` and `spawn` in the process library, or `execv` with a `ptr<ptr<uint8>?>` array.

### 5. open with a mode: a pid file

```dewy
# Take a pid-file lock: create it only if absent, readable by all, writable by us.
$extern(name='open')
c_open = (path:string flags:int32 ...args):>int32
$extern
write = (fd:int32 data:ptr<uint8> count:uint64):>int64
$extern
close = (fd:int32):>int32
$extern
getpid = ():>int32
const O_WRONLY:int32 = 0o1
const O_CREAT:int32 = 0o100
const O_EXCL:int32 = 0o200
const MODE_644:int32 = 0o644

main = () => $unsafe {
    let fd = c_open("demo.pid" O_WRONLY | O_CREAT | O_EXCL MODE_644)
    if fd <? 0 { printl"already running"; exit(1) }
    let text = bytes("{getpid()}\n")
    write(fd text.ptr uint64(text.length));
    close(fd);
    printl"locked"
}
```

| Obvious | Discoverable | Concise | Safe | Complete |
|---|---|---|---|---|
| 5 | 4 | 4 | 3 | 5 |

- Concise 4: the mode needs a typed constant because a bare `0o644` is an `int` (same gap as 1).
- Safe 3: `O_CREAT` without a mode compiles and creates a file with stack-garbage permissions, as
  in C. The file library (`write_file` and friends) is the safe route.
- `mode_t` is promoted to `int` on every target, so `int32` is right on Linux and macOS.
- Compared: identical in Rust; Python's `os.open(path, flags, mode=0o777)` has a default; Go has
  `syscall.Open(path, flags, mode)` with a fixed signature.

### 6. fcntl: zero, one integer, or one pointer extra

```dewy
# Make a pipe's read end non-blocking, then take a write lock on a data file.
Flock:type = [kind:int16 whence:int16 start:int64 length:int64 pid:int32]
$extern
fcntl = (fd:int32 command:int32 ...args):>int32
$extern(name='open')
c_open = (path:string flags:int32 ...args):>int32
$extern
pipe = (fds:ptr<int32>):>int32
const F_GETFL:int32 = 3
const F_SETFL:int32 = 4
const F_SETLK:int32 = 6
const O_RDWR:int32 = 0o2
const O_NONBLOCK:int32 = 0o4000
const F_WRLCK:int16 = 1

main = () => $unsafe {
    let fds:array<int32> = [0 0]
    if pipe(fds.ptr) not=? 0 return
    let flags = fcntl(fds[0] F_GETFL)
    fcntl(fds[0] F_SETFL flags | O_NONBLOCK);
    printl((fcntl(fds[0] F_GETFL) & O_NONBLOCK) not=? 0)
    let fd = c_open("data.db" O_RDWR)
    let lock:array<Flock> = [Flock[F_WRLCK 0 0 0 0]]
    if fd >=? 0 and fcntl(fd F_SETLK lock.ptr) =? 0 { printl"locked data.db" }
}
```

| Obvious | Discoverable | Concise | Safe | Complete |
|---|---|---|---|---|
| 5 | 4 | 5 | 3 | 5 |

- One declaration serves all three call shapes, which is why the extras must be untyped. Safe 3
  for the same reason as `ioctl`: the command decides the extra.
- Compared: Rust and cffi are the same; Go uses fixed-signature wrappers in `syscall`.

### 7. syslog: a daemon's log

```dewy
# A sensor daemon logs through syslog.
$extern
openlog = (ident:ptr<uint8> option:int32 facility:int32):>void
$extern
syslog = (priority:int32 format:string ...args):>void
$extern
strdup = (s:string):>ptr<uint8>?
const LOG_PID:int32 = 1
const LOG_DAEMON:int32 = 24
const LOG_INFO:int32 = 6
const LOG_WARNING:int32 = 4

main = () => $unsafe {
    let ident = strdup("sensord") ?? return   # openlog keeps the pointer: give it C memory
    openlog(ident LOG_PID LOG_DAEMON)
    let reading:float32 = 21.5
    syslog(LOG_INFO "sensor %s reads %.1f C" "porch" reading)
    let label = read_line()
    if label is? string {
        syslog(LOG_WARNING "relabelled: %s" label)
        syslog(LOG_WARNING "relabelled: {label}")   # compiles; a % in label is undefined
    }
}
```

| Obvious | Discoverable | Concise | Safe | Complete |
|---|---|---|---|---|
| 4 | 4 | 5 | 1 | 5 |

- Safe 1: the second `syslog` is the classic format injection, and Dewy makes it easier to write
  than C does: an interpolated string looks like the natural way to build the message.
  `syslog(LOG_WARNING label)` is the same bug.
- Obvious 4: `openlog` keeps its `ident` pointer, so a Dewy string (a copy made for the call) or
  an array's `.ptr` dangles later (FFI: retained pointers).
- The `float32` crosses as a `double`, as `%f` expects.
- Compared: GCC warns on `syslog(p, s)` (`-Wformat-security`) because glibc marks `syslog` with a
  format attribute; Rust, ctypes, cffi have no check; Swift and Go need wrappers.

### 8. sscanf: pointer out-parameters

```dewy
# Parse a display mode like "1920x1080@59.94" exactly as the C config reader did.
$extern
sscanf = (text:string format:string ...args):>int32

Mode:type = [width:int32 height:int32 refresh:float64]

parse_mode = (text:string):>Mode | none => $unsafe {
    let w:array<int32> = [0]
    let h:array<int32> = [0]
    let hz:array<float64> = [0.0]
    if sscanf(text "%dx%d@%lf" w.ptr h.ptr hz.ptr) not=? 3 return none
    Mode[w[0] h[0] hz[0]]
}

main = () => loop text in ["1920x1080@59.94" "800x600" "bogus"] {
    let m = parse_mode(text)
    if m is? none { printl"{text}: not a mode" }
    else { printl"{text}: {m.width} by {m.height} at {m.refresh} Hz" }
}
```

| Obvious | Discoverable | Concise | Safe | Complete |
|---|---|---|---|---|
| 5 | 4 | 4 | 3 | 5 |

- Promotions apply to values, not to what a pointer points at: `%f` needs a `ptr<float32>`,
  `%lf` a `ptr<float64>`. D51 does not say so; a reader who learned "float32 goes as double" may
  expect the pointer case to be fixed up too.
- Concise 4, discoverable 4: one-element arrays as out-parameter cells (FFI).
- Safe 3: the count check catches a short parse; pointer types against the format do not.
- Compared: Rust `&mut w`, ctypes `byref(c_int())`, Swift `withUnsafeMutablePointer`; same safety.

### 9. A C logging library: the systemd journal

```dewy
# Log a backup job to the systemd journal, with a structured field.
$extern(lib='libsystemd.so.0')
sd_journal_print = (priority:int32 format:string ...args):>int32
$extern(lib='libsystemd.so.0')
sd_journal_send = (format:string ...args):>int32
const LOG_INFO:int32 = 6

main = () => $unsafe {
    let job = "backup"
    let seconds:float64 = 12.75
    let files:int32 = 4096
    sd_journal_print(LOG_INFO "%s finished in %.2f s" job seconds);
    sd_journal_send("MESSAGE=%s finished" job "JOB_FILES=%d" files "PRIORITY=%i" LOG_INFO none);
}
```

| Obvious | Discoverable | Concise | Safe | Complete |
|---|---|---|---|---|
| 5 | 4 | 5 | 2 | 4 |

- `sd_journal_send` interleaves formats with their arguments and ends with a null: no declaration
  can type it, and it needs the same `none` rule as `execl` (complete 4).
- Safe 2: format and sentinel unchecked, as in C.
- Compared: same in Rust and cffi; Go's `go-systemd/journal` reimplements the protocol rather than
  calling the variadic functions.

### 10. A callback that receives a `va_list`: FFmpeg's log

```dewy
# Route FFmpeg's log lines into ours: its callback hands over a va_list for vsnprintf.
$extern(lib='libavutil.so.59')
av_log_set_callback = (callback:((ctx:ptr<uint8>? level:int32 format:ptr<uint8> args:ptr<uint8>):>void)):>void
$extern(lib='libavutil.so.59')
av_log = (ctx:ptr<uint8>? level:int32 format:string ...args):>void
$extern
vsnprintf = (buf:ptr<uint8> size:uint64 format:ptr<uint8> args:ptr<uint8>):>int32
const AV_LOG_INFO:int32 = 32

$export
on_av_log = (ctx:ptr<uint8>? level:int32 format:ptr<uint8> args:ptr<uint8>):>void => $unsafe {
    if level >? AV_LOG_INFO return
    let buf:array<uint8> = [loop _ in [0..512) uint8(0)]
    let n = vsnprintf(buf.ptr 512 format args)
    if n <? 0 return
    printl"[ffmpeg] {(buf[$clamp 0..n) as string | none ?? "?").remove_suffix("\n")}"
}

main = () => $unsafe {
    av_log_set_callback(@on_av_log)
    let rate:int32 = 48000
    av_log(none AV_LOG_INFO "decoder %s opened at %d Hz\n" "opus" rate)
}
```

| Obvious | Discoverable | Concise | Safe | Complete |
|---|---|---|---|---|
| 3 | 2 | 4 | 3 | 4 |

- `va_list` as `ptr<uint8>` works as a parameter on every native ABI (an array that decays on
  x86-64 System V, `char *` on Apple arm64 and Windows, a struct passed by reference on Linux
  arm64), but a reader has to know that (obvious 3, discoverable 2). Dewy cannot build or read a
  `va_list`, only pass one on (complete 4). This is next to D51, not part of it.
- Compared: Swift has `CVaListPointer`; Rust's `VaList` is unstable; cffi has no `va_list` type
  either and needs the same trick; Go cannot export a function taking one.

### 11. A wrapper that forwards to a variadic function

```dewy
# warn() prefixes the tool's name and writes to stderr through C, sharing C's stream.
$extern
dprintf = (fd:int32 format:string ...args):>int32
const STDERR:int32 = 2

warn = (format:string):>void => $unsafe {
    dprintf(STDERR "mytool: "); dprintf(STDERR format); dprintf(STDERR "\n");
}
warn = <A>(format:string a:A):>void => $unsafe {
    dprintf(STDERR "mytool: "); dprintf(STDERR format a); dprintf(STDERR "\n");
}
warn = <A B>(format:string a:A b:B):>void => $unsafe {
    dprintf(STDERR "mytool: "); dprintf(STDERR format a b); dprintf(STDERR "\n");
}

main = () => {
    let skipped:int32 = 3
    warn("config not found, using defaults")
    warn("%d files skipped" skipped)
    warn("%s: %d" "retry" skipped)
}
```

| Obvious | Discoverable | Concise | Safe | Complete |
|---|---|---|---|---|
| 3 | 3 | 2 | 3 | 3 |

- `stderr` is a C variable, and `$extern` declares only functions, so the program uses `dprintf`
  on fd 2 (FFI).
- A Dewy rest parameter (`...xs:T`) takes one shared type, so a heterogeneous forward needs one
  generic overload per count (concise 2, complete 3). `warn("%d files" 3)` infers `A` as `int` and
  fails inside the wrapper, far from the call.
- Compared: Python forwards `*args` for free; Swift takes `CVarArg...` and calls `withVaList`;
  Rust cannot define a variadic function on stable and uses a macro; Go and TypeScript cannot
  call the target at all.

### 12. A float32 and a bool cross: a frame-stats line

```dewy
# A game's frame-stats overlay text, formatted by the C side's conventions.
$extern
snprintf = (buf:ptr<uint8> size:uint64 format:string ...args):>int32

Stats:type = [frame_ms:float32 vsync:bool layer:uint8]

hud_line = (s:Stats):>string => $unsafe {
    let buf:array<uint8> = [loop _ in [0..64) uint8(0)]
    let n = snprintf(buf.ptr 64 "%5.2f ms  vsync=%d  layer=%u" s.frame_ms s.vsync s.layer)
    buf[$clamp 0..int(n)) as string | none ?? "?"
}

main = () => {
    printl(hud_line(Stats[16.67 true 2]))
    printl(hud_line(Stats[33.4 false 0]))
}
```

| Obvious | Discoverable | Concise | Safe | Complete |
|---|---|---|---|---|
| 5 | 5 | 4 | 3 | 5 |

- `float32` goes as `double`, `bool` and `uint8` as `int`: exactly what `%f`, `%d` and `%u` read,
  with nothing written. The backends already do this (tests/fixtures/core_ffi/variadic.c).
- Compared: Rust rejects `f32`, `bool` and `u8` here (E0617) and asks for casts; cffi asks for
  casts; Swift promotes `Float` itself. D51's promotion is the friendlier of the two answers and
  equally exact.

### 13. A library that returns memory: SQLite's quoting printf

```dewy
# Build an SQL statement with SQLite's own quoting: %q doubles single quotes.
$extern(lib='libsqlite3.so.0')
sqlite3_mprintf = (format:string ...args):>ptr<uint8>?
$extern(lib='libsqlite3.so.0')
sqlite3_free = (p:ptr<uint8>?):>void
$extern
strlen = (s:ptr<uint8>):>int64<(>=? 0)>

c_text = (p:ptr<uint8>):>string => $unsafe {
    let out:array<uint8> = []
    loop i in [0..strlen(p)) { out.push(p[i]) }
    out as string | none ?? "?"
}

insert_sql = (name:string city:string):>string => $unsafe {
    let p = sqlite3_mprintf("INSERT INTO people VALUES('%q', '%q');" name city) ?? return "?"
    let sql = c_text(p)
    sqlite3_free(p)
    sql
}

main = () => printl(insert_sql("O'Brien" "Dún Laoghaire"))
```

| Obvious | Discoverable | Concise | Safe | Complete |
|---|---|---|---|---|
| 5 | 4 | 4 | 3 | 4 |

- Complete 4: `%Q` writes `NULL` for a null pointer, but a `string | none` cannot cross, so an
  optional column needs two calls or a `ptr<uint8>?` made by hand (FFI, and the extras inherit it).
- Discoverable 4, concise 4: copying a C string into a Dewy string by hand (FFI).
- Compared: Rust and ctypes the same; Python's `sqlite3` module uses bound parameters instead.

### 14. What the errors say

```dewy
$extern
printf = (format:string ...args):>int32
Point:type = [x:float64 y:float64]

main = () => $unsafe {
    let count = 0
    loop _ in [0..3) { count += 1 }
    printf("%d\n" count);                # count is int
    let ratio = 1/3
    printf("%f\n" ratio);                # ratio is rational
    printf("%f %f\n" Point[1.0 2.0]);    # a record by value
    let names:array<string> = []
    names.push("a")
    printf("%s\n" names...);             # a spread whose length is not known
}
```

| Obvious | Discoverable | Concise | Safe | Complete |
|---|---|---|---|---|
| 4 | 2 | 5 | 4 | 3 |

- D51 says these are errors but not what they say or how to fix them (discoverable 2), and is
  silent on spreads (complete 3).

### Round 0 summary

| Program | O | D | C | S | Cm |
|---|---|---|---|---|---|
| 1 printf | 5 | 3 | 4 | 2 | 4 |
| 2 snprintf | 4 | 3 | 3 | 3 | 5 |
| 3 ioctl | 5 | 4 | 5 | 3 | 5 |
| 4 execl | 4 | 3 | 5 | 1 | 4 |
| 5 open | 5 | 4 | 4 | 3 | 5 |
| 6 fcntl | 5 | 4 | 5 | 3 | 5 |
| 7 syslog | 4 | 4 | 5 | 1 | 5 |
| 8 sscanf | 5 | 4 | 4 | 3 | 5 |
| 9 journal | 5 | 4 | 5 | 2 | 4 |
| 10 va_list callback | 3 | 2 | 4 | 3 | 4 |
| 11 forwarding wrapper | 3 | 3 | 2 | 3 | 3 |
| 12 float32 and bool | 5 | 5 | 4 | 3 | 5 |
| 13 sqlite3_mprintf | 5 | 4 | 4 | 3 | 4 |
| 14 errors | 4 | 2 | 5 | 4 | 3 |

The spelling itself read well everywhere: nobody needs to look twice at
`printf = (format:string ...args):>int32`, and one declaration covers `fcntl`'s three call
shapes. The low grades come from semantics D51 leaves unsaid, from diagnostics, and from format
strings, which no rule on untyped extras can check.

## Iteration 1: semantics and diagnostics (no new syntax)

**R1. Literals in the extras take C's types.** An integer literal crosses as `int32` when it fits,
otherwise `int64` (C's rule for an unsuffixed constant; Rust does the same with `i32`). A decimal
literal crosses as `float64`, `true`/`false` as `int32` like any `bool`, and `none` as a null
pointer. A string literal is already a `char *`. Without R1, D51's own example
(`printf("%d apples, %s\n" 3 "red")`, `open("log.txt" 65 420)`) does not compile. A *binding*
still needs a fixed-width type, because its width decides `%d` against `%ld`.
Fixes 1, 4, 5, 9 (the `none` sentinel crosses; `open(... 0o644)` needs no constant).

**R2. Diagnostics that name the fix.** Proposed text:

- `int`: "`count` is an `int`, which has no fixed size in C: write `int32(count)` for `%d` or
  `int64(count)` for `%ld`." The fix-it offers both.
- `rational`: "`ratio` is a `rational`; C reads a `double`: write `float64(ratio)`."
- Record by value: "a variadic C function cannot take the record `Point` by value: pass its
  fields, or a `ptr<Point>` (`cell.ptr`) if the C side expects a pointer."
- An error from inside a generic wrapper (program 11) names the outermost call whose argument
  chose the type, with the same fix-it there.
- `string | none` and other unions: "`note` may be `none`: a C extra has one type; pass
  `note ?? ""` or decide before the call." (A nullable C string is the FFI gap below.)

Fixes 1, 11, 14.

**R3. Spreads into the extras.** `xs...` spreads an array whose length is known when compiling
(a fixed array, or a rest parameter's written arguments), each element crossing as an extra; an
array of unknown length is an error: "the number of a C function's extra arguments is fixed at
each call: spread a fixed-length array, or call a function that takes an array (`execv`)". This is
what the existing spread rule already implies. Fixes 14; lets a homogeneous wrapper forward.

**R4. Two format warnings, from facts the compiler already has.** The format of a variadic C call
is taken to be its last fixed `string` parameter (true of every function in this round). Then:

- An interpolated string there warns: "`{label}` puts text into a C format, where a `%` in it is
  undefined: pass it as an argument, `syslog(LOG_WARNING "relabelled: %s" label)`." The fix-it
  rewrites each `{x}` as `%s` with `x` appended when `x` is a `string`; otherwise it only warns.
- A non-constant string there with no extras warns the same way (`syslog(LOG_WARNING label)`),
  unless it is a parameter of the calling function (a wrapper passing its own format on, as in 11).

This is a Dewy-specific hazard: interpolation is how Dewy builds text, so `printf("hi {name}\n")`
is the natural thing to write. Fixes most of 7's safe grade.

**R5. A typed rest parameter on an `$extern` checks every extra.** Dewy already spells a rest
parameter `...xs:T`; on an `$extern` it would mean every extra is a `T`. A program can then
declare a checked view of one call shape without the undefined fixed declaration:

```dewy
$extern(name='ioctl')
ioctl_winsize = (fd:int32 request:uint64 ...out:ptr<WinSize>):>int32
```

The count stays open (C cannot check it), but the type is checked. This is the existing spelling
in a new place, a natural extension rather than a new one; reported for David. Raises 3 and 6.

**R6. Say in LANGUAGE.md:** promotions apply to values, not pointees (`%f` in `sscanf` takes
`ptr<float32>`); C's stdout buffer is separate from `printl`'s, so flush before mixing; prefer
`execv`/`run` over `execl`. Raises 1 and 8.

Considered and rejected: warning when an `$extern` names a known variadic C function (`printf`,
`open`, `ioctl`) declared with fixed parameters. It would catch the undefined declaration D51
exists to replace, but a table of C names in the compiler is the kind of magic Dewy avoids; the
check belongs to a future C header import, which would know every signature.

### Grades after iteration 1

| Program | O | D | C | S | Cm | Still short because |
|---|---|---|---|---|---|---|
| 1 printf | 5 | 5 | 4 | 3 | 5 | format unchecked; flush line (FFI) |
| 2 snprintf | 4 | 3 | 3 | 3 | 5 | buffer and string boilerplate (FFI) |
| 3 ioctl | 5 | 4 | 5 | 4 | 5 | platform constants (FFI); count unchecked |
| 4 execl | 5 | 5 | 5 | 1 | 5 | missing `none` is undefined, inherently |
| 5 open | 5 | 4 | 5 | 3 | 5 | missing mode with `O_CREAT`, inherently; constants (FFI) |
| 6 fcntl | 5 | 4 | 5 | 4 | 5 | command decides the extra |
| 7 syslog | 4 | 5 | 5 | 4 | 5 | retained `ident` pointer (FFI) |
| 8 sscanf | 5 | 5 | 4 | 3 | 5 | pointer types unchecked; out-param cells (FFI) |
| 9 journal | 5 | 5 | 5 | 2 | 5 | interleaved formats and sentinel, inherently |
| 10 va_list callback | 3 | 2 | 4 | 3 | 4 | no name for `va_list` |
| 11 forwarding wrapper | 4 | 4 | 2 | 3 | 3 | no heterogeneous forward |
| 12 float32 and bool | 5 | 5 | 4 | 3 | 5 | format unchecked; buffer (FFI) |
| 13 sqlite3_mprintf | 5 | 4 | 4 | 3 | 4 | C string copy, nullable string (FFI) |
| 14 errors | 5 | 5 | 5 | 5 | 5 | |

## Iteration 2: what would need new surface (David's call)

**N1. Format checking for printf-style functions.** A keyword on `$extern` naming the format
convention, checked like Dewy's own `fmt'...'` patterns already are: a literal format is read
while compiling and each extra's type must fit its conversion (`%d` an `int32`, `%ld` an `int64`,
`%s` a string or `ptr<uint8>`, `%f` a float, `%lf` in `scanf` a `ptr<float64>`); a non-literal
format is unchecked, with R4's warnings. This is GCC's `format` attribute. Candidate spelling
`$extern(format='printf')` (also `'scanf'`); **new spelling, not yet cold-tested**. Recommended:
yes, as its own decision after D51; additive and reversible. It moves safe to 5 on 1, 12 and
(for literal formats) 2, 7, 8, 9's `sd_journal_print`, 10's `av_log`, 11 and 13; `ioctl`, `fcntl`,
`open`'s mode and sentinels stay outside any format check.

**N2. Forwarding a bundle from a Dewy function.** The archived reference gives the direction for
Dewy's own `...rest`: capture the arguments no earlier parameter claims, and forward the bundle
with `...`. An untyped `...args` on a Dewy function would be that bundle, specialized per call, so
program 11 becomes one function:

```dewy
warn = (format:string ...args):>void => $unsafe {
    dprintf(STDERR "mytool: "); dprintf(STDERR format args...); dprintf(STDERR "\n");
}
```

Same spelling as D51; **new semantics for Dewy functions**, so it needs a design pass on bundle
types (named arguments, lambdas). Recommended: take it as the direction, decide it separately;
D51 does not depend on it. With N1 the wrapper could also carry `format=` so its callers' formats
are checked.

**N3. A name for `va_list`.** Program 10 works with `ptr<uint8>`, but only by ABI coincidence a
reader must know. A library type for it (Swift's `CVaListPointer`) would make the callback obvious.
**New name, not cold-tested.** Recommended: defer until a second program needs it; document the
`ptr<uint8>` rule meanwhile.

**Not proposed: a sentinel marker** (`execl`, `sd_journal_send`, GCC's `sentinel` attribute). It
would catch a missing final `none` but not a wrong count before it, and the safe routes
(`execv`, `run`, `spawn`) already exist. `execl` stays at safe 1: it is C-unsafe by contract.

### Final grades (iteration 1, plus N1 and N2 if accepted)

| Program | O | D | C | S | Cm |
|---|---|---|---|---|---|
| 1 printf | 5 | 5 | 4 | 5 (N1) | 5 |
| 2 snprintf | 4 | 3 | 3 | 4 (N1) | 5 |
| 3 ioctl | 5 | 4 | 5 | 4 | 5 |
| 4 execl | 5 | 5 | 5 | 1 | 5 |
| 5 open | 5 | 4 | 5 | 3 | 5 |
| 6 fcntl | 5 | 4 | 5 | 4 | 5 |
| 7 syslog | 4 | 5 | 5 | 5 (N1) | 5 |
| 8 sscanf | 5 | 5 | 4 | 5 (N1) | 5 |
| 9 journal | 5 | 5 | 5 | 3 (N1) | 5 |
| 10 va_list callback | 3 | 2 | 4 | 4 (N1) | 4 |
| 11 forwarding wrapper | 5 (N2) | 5 (N2) | 5 (N2) | 4 (N1) | 5 (N2) |
| 12 float32 and bool | 5 | 5 | 4 | 5 (N1) | 5 |
| 13 sqlite3_mprintf | 5 | 4 | 4 | 4 (N1) | 4 |
| 14 errors | 5 | 5 | 5 | 5 | 5 |

D51's own part (declaring and calling, with R1-R6) reaches 5 on obvious, discoverable, concise and
complete wherever the program's remaining gap is not general FFI. What stays under 5:

- **Safe**, for anything without a checkable format: `execl` and `sd_journal_send` sentinels,
  `open`'s mode, the `ioctl`/`fcntl` command-to-argument pairing. These are C contracts; no
  declaration of untyped extras can see them. R5's typed views narrow `ioctl` and `fcntl`.
- **Format checking** needs N1.
- **Heterogeneous wrappers** need N2.
- **General FFI**, outside D51: copying a C string or a filled buffer into a Dewy string; a
  zero-filled buffer; out-parameter cells; platform constants without a header import; `errno`;
  C variables (`stderr`); pointers C keeps after the call (`openlog`'s `ident`); a nullable string
  (`string | none` as `char *` or null); whether C's stdout buffer is flushed when a program exits.

## Recommendations

1. Accept D51 Q1 (`...args`) as proposed; the spelling graded 5 on obvious in every program.
2. Take R1 (literals cross with C's types, `none` as null) as part of D51: the D51 example needs it.
3. Take R2 (diagnostic text), R3 (fixed-length spreads), R4 (two format warnings) and R6 (docs):
   semantics and diagnostics, no new syntax.
4. Report R5 (typed rest `...out:T` on an `$extern`) as a natural extension of the existing rest
   spelling; implement with D51.
5. Bring N1 (`$extern(format='printf')`) to David as a separate item after a cold read and its own
   dogfood; recommend yes.
6. Record N2 (untyped `...args` bundles on Dewy functions) as the direction from the archive, for
   its own design round. Defer N3.
