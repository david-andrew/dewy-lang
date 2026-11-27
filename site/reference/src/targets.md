# Targets: Native, Web, and GPU

> [Generated coverage](/status/#ref-targets) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

A target is the machine and system a program is compiled for. The default is the machine running the compiler. The same source builds a native executable or a self-contained web page, and numeric array work can run on a GPU.

## Target Names

A target name has only the fields it needs: the processor, then the system.

| Names | Target |
|---|---|
| `x86_64`, `aarch64`, `riscv64`, `c` | this machine's system on that processor |
| `x86_64-linux`, `aarch64-linux`, `riscv64-linux`, `c-linux` | Linux |
| `x86_64-mac`, `aarch64-mac` | macOS |
| `x86_64-windows`, `aarch64-windows`, `riscv64-windows`, `c-windows` | Windows |
| `x86_64-freestanding`, `aarch64-freestanding`, `riscv64-freestanding`, `c-freestanding` | bare metal |
| `c-posix`, `c89`, `wasm32` | portable C, and WebAssembly in the browser |

The current compiler builds `x86_64-linux`, `aarch64-linux`, `aarch64-mac`, `x86_64-windows` and `wasm32`. Any other name from the table is an error saying it is not supported yet; a name not in the table is an unknown target.

```sh
dewy build game.dewy --target x86_64-windows -o game.exe
dewy build game.dewy --target wasm32 -o game.html
dewy build game.dewy --target riscv64-linux -o game
# dewy: target 'riscv64-linux' is not supported yet (the supported targets are x86_64-linux, aarch64-linux, aarch64-mac, x86_64-windows, wasm32)
```

Further target names (CPU levels, OS version floors, `host`) are under review.

## `$target` and `$build`

`$target` is the full name of the target being compiled for (`x86_64-linux`, `wasm32`, …), never a processor alone. `$target.arch` is its processor (`x86_64`, `aarch64`, `riscv64`, `c` or `wasm32`) and `$target.os` its system (`linux`, `mac`, `windows`, `freestanding`, `posix`, or `none` for `wasm32` and `c89`). `$build.mode` is `'debug'` or `'release'`.

A condition made only of these compared with string literals (`=?`, `not =?`, `in?` and `not in?` a literal list, joined by `not`, `and` and `or`) is decided while compiling. Its `if` compiles only the live arm and splices that arm's body into the enclosing scope, so declarations and imports there bind as if written outside. The other arms are never checked, so they may name modules or functions that exist only on another target.

<!-- dewy-example: {"mode":"run","stdout":"a native program\n"} -->
```dewy
if $target =? "wasm32" {
    describe = () => "a web page"
} else if $target.os in? ["linux" "mac" "windows"] {
    describe = () => "a native program"
} else {
    describe = () => "something else"
}
printl(describe())
```

A misspelled name is an error, not a condition that is always false:

<!-- dewy-example: {"mode":"reject","diagnostic":"unknown system \"linux2\""} -->
```dewy
if $target.os =? "linux2" { printl"never" }
```

Elsewhere, `$target` and its members are ordinary strings.

### Setting the Target and Mode

The entry file may set the target and the build mode, each once, at the top level on a line of its own:

<!-- dewy-example: {"mode":"check"} -->
```dewy
$target = 'wasm32'
$build.mode = 'release'

main = () => printl"built for {$target}"
```

`--target`, `--release` and `--debug` on the command line override the file, with a warning naming both when they differ. An output name ending in `.html`, `.zip` or `.exe` picks the target when neither sets one. Only the target and the mode come from the command line; every other setting is written in the source.

### `$supported_targets`

`$supported_targets` lists the full target names a module accepts, once at file scope. Compiling it for any other target is an error:

<!-- dewy-example: {"mode":"reject","diagnostic":"this module supports wasm32, not"} -->
```dewy
$supported_targets = ["wasm32"]
printl"web only"
```

## Native Targets

A native build is a single executable; Linux executables are statically linked. Foreign functions load their libraries when first called (see [Host Interoperability](interoperability.md)).

`--target` cross-compiles: a Linux x86-64 host builds every supported target. A Windows build also writes a `.pdb` debug database beside the `.exe`.

## WebAssembly

`--target wasm32` emits one self-contained HTML page: the compiled program, its runtime and its embedded assets in a single file, with no other files to serve.

```sh
dewy build hello.dewy --target wasm32 -o hello.html
```

Console output goes to the page and to the browser's console. Games draw to a canvas and use WebGL 2 where available. Assets embedded with `$include_bytes` are included in web builds too.

### What Differs on the Web

The language is the same on every target; what the page's host can do differs.

| Facility | On the web |
|---|---|
| `parallel` loops and blocks | run serially, with the same results, order and copy semantics |
| `concurrent` and `spawn` (tasks) | a compile error: the web runs one thread |
| Files | live in the page's memory; directories exist as the paths of files and of `mkdir` |
| Processes (`run`, `capture`, …) | always `SpawnError` |
| TCP sockets (`net.tcp_*`) | none, so a page cannot listen for connections; WebSocket game messages (`net.connect`, `net.send`) work |
| GPU arrays | WebGL 2 where available, else the CPU fallback |
| Foreign functions | imported from the page by their Dewy name |

<!-- dewy-example: {"mode":"reject","diagnostic":"tasks need a native target (the web runs one thread)"} -->
```dewy
$target = 'wasm32'
work = (n:int) => n*2
main = () => {
    concurrent {
        let a = spawn work(21)
    }
    printl(a ?? 0)
}
```

The same program with `parallel` instead compiles for the web and runs serially:

<!-- dewy-example: {"mode":"check"} -->
```dewy
$target = 'wasm32'
let doubled = [parallel i in [0..4) i*2]
printl(doubled)
```

## GPU Arrays

`gpu(values)` uploads a numeric array or `NDArray`; `cpu(value)` downloads an independent `NDArray` with the same shape. Placement follows the data: an expression on GPU arrays runs on the GPU, and its result stays there until downloaded.

<!-- dewy-example: {"mode":"check"} -->
```dewy
height = (x:float32 y:float32):>float32 => x*x + y

main = () => {
    let xs = gpu([1.0 2.0 3.0])
    let shifted = xs .* 2.0 .+ 1.0
    printl(cpu(shifted).data)          # [3.0 5.0 7.0]
    printl(cpu(xs).data)               # [1.0 2.0 3.0]: the upload is unchanged
    printl(sum(shifted))               # 15.0
    printl(cpu(height.(xs xs)).data)   # [2.0 6.0 12.0]
}
```

- Floating inputs become `float32`. Integer inputs become `int32<overflow='wrap'>`, the GPU's modular word format. Arrays may have up to four dimensions.
- Adjacent dotted operations fuse into one GPU program, including calls to named functions written in Dewy. Shapes broadcast as on the CPU.
- `sum`, `min`, `max` and `mean` accept GPU arrays. Comparisons give `float32` masks of zeros and ones.
- The uploaded value and saved copies stay unchanged. Upload reusable inputs once and download where CPU code needs the result.
- A download of an upload keeps its shape. A GPU program's result has a shape known only when it runs: a guard or a check states it.

<!-- dewy-example: {"mode":"check"} -->
```dewy
main = () => {
    let xs = gpu([1.0 2.0 3.0 4.0])
    printl(cpu(xs .>? 2.0).data)                # [0.0 0.0 1.0 1.0]
    printl"{min(xs)} {max(xs)} {mean(xs)}"      # 1.0 4.0 2.5
    let row:array<float32> = [1.0 2.0 3.0]
    let column:array<float32> = [10.0 20.0]
    let grid = gpu(reshape(row 1 3)) .+ gpu(reshape(column 2 1))
    let back = cpu(grid)
    if back.length =? [2 3] printl(back[1 2])   # 23.0
}
```

### Mixing Devices

An expression cannot mix a GPU array with an array in CPU memory. It is a compile error, never a hidden copy; upload the other operand, or download the GPU one:

<!-- dewy-example: {"mode":"reject","diagnostic":"this array is in CPU memory: upload it with gpu(xs)"} -->
```dewy
main = () => {
    printl(cpu(gpu([1.0 2.0]) .+ [3.0 4.0]))
}
```

### What Runs on a GPU

GPU functions are checked at compile time, also when the CPU fallback will run them:

- They use shader-compatible numbers. A shader holds 32-bit words, so a 64-bit integer in GPU memory is an error (declare it `int32` or `uint32`), and a 64-bit local must be proven to fit a word.
- A shader cannot run a check, so every obligation in a GPU function (overflow, a divisor, a conversion, an index) must be proven, even under `$runtime_checks`. Wrapping types need no overflow proof.
- They cannot capture variables, print, or allocate managed collections.
- Exact rational division is a CPU operation; use floating inputs for `./`.

<!-- dewy-example: {"mode":"reject","diagnostic":"a shader cannot run a check"} -->
```dewy
scale = (x:int64):>int64 => x*2
main = () => {
    printl(cpu(scale.(gpu([1 2 3]))).data)
}
```

<!-- dewy-example: {"mode":"reject","diagnostic":"captures variables cannot run on the GPU"} -->
```dewy
main = () => {
    let offset = float32(1.0)
    let shift = (x:float32) => x + offset
    printl(cpu(shift.(gpu([1.0 2.0]))))
}
```

A GPU buffer holds at most `int32.max` elements; more is a GPU capacity failure.

### Drivers and the CPU Fallback

Native Linux programs try Vulkan, then offscreen GLES; browser builds use WebGL 2. `gpu_available()` reports whether a driver is active. Otherwise, including under Node and with `DEWY_SOFTWARE=1`, the same expressions run on the CPU with the same results. Single-precision GPU math can differ slightly from CPU results.

[`examples/terrain_array.dewy`](https://github.com/david-andrew/dewy-lang/blob/master/examples/terrain_array.dewy) broadcasts two axes into a height field with a Dewy function and compares the download with a CPU calculation.
