# The Standard Library

This is a tour of what the libraries give you. Each section has one small example and a pointer to where the details live. Some things need no import at all (they live in the prelude, see [Modules, Imports, and the Prelude](../ch03/imports.md)); the rest are one `import` away.

The compiler finds its matching libraries beside the standalone executable. `dewy-core --print-lib` prints the active library directory. In a checkout the source is [`lib/`](https://github.com/david-andrew/dewy-lang/blob/master/lib/). Host services have target-specific constraints; native coverage does not imply browser support.

## Collections

Arrays, dictionaries and sets are built in. Loop over a dictionary with `[key value]`. [Container Types](../ch03/container-types.md) teaches them in full.

<!-- dewy-example: {"mode": "run", "stdout": "ada: 2\nalan: 5\n2\n[1 2 3]\n6\ntrue\n"} -->
```dewy
let counts = ["ada" -> 1]
counts["ada"] += 1
counts["alan"] = 5
loop [k v] in counts printl"{k}: {v}"
printl(counts.length)

let xs = [3 1 2]
xs.sort()
printl(xs)
printl(xs.sum)
printl("a" in? set["a" "b"])
```

Numeric arrays also support elementwise arithmetic with dotted operators, matrices and solvers, and arrays can run on the GPU. The [language guide](https://github.com/david-andrew/dewy-lang/blob/master/docs/LANGUAGE.md#numeric-arrays-and-matrices) covers those.

## Text

Strings have the methods you would look for: `split`, `trim`, `upper`, `repeat`, and more. Methods that take no arguments are written like fields, with no parentheses. `fmt` formats numbers.

<!-- dewy-example: {"mode": "run", "stdout": "[\"a\" \"b\" \"c\"]\nHELLO\nxxx\n0.67\n"} -->
```dewy
printl("a,b,c".split(","))
printl("hello".upper)
printl("x".repeat(3))
printl(fmt'.2f'(2.0/3))
```

## Math

`min`, `max`, `abs`, `sqrt`, `sin`, `cos` and the other usual functions are in the prelude. Angle functions take an angle, so a degree sign or `rad` goes with the number (see [Physical Quantities and Units](../ch03/units.md)).

<!-- dewy-example: {"mode": "run", "stdout": "3\n4\n4.0\n0.5\n"} -->
```dewy
from units import °
printl(min(3 9))
printl(abs(-4))
printl(sqrt(16.0))
printl(sin(30°))
```

## Exact integers and fractions

Integers never overflow by default. `bigint` is the same arbitrary-precision type, and dividing two integers gives an exact fraction.

<!-- dewy-example: {"mode": "run", "stdout": "15241578753238836750495351562536198787501905199875019052100\n115792089237316195423570985008687907853269984665640564039457584007913129639936\n5/6\n0.0(3)\n"} -->
```dewy
let value:bigint = 123456789012345678901234567890
printl(value*value)
printl(bigint(2)^256)
printl(1/2 + 1/3)
printl(0.1/3)
```

A repeating decimal prints with its repeat in parentheses. `rational("-7/3")` reads a fraction from text.

## Time and dates

Time needs no import. `now` reads the clock, and subtracting two readings measures elapsed time. A date is written `date"2026-12-25"`, checked while compiling. Subtracting dates gives a period you can divide by a calendar unit.

<!-- dewy-example: {"mode": "run", "stdout": "62\n2026-12-26\n90min\n"} -->
```dewy
printl((date"2026-12-25" - date"2026-10-24") / 1day)
printl(date"2026-12-25" + 1day)
printl(90minute)
```

Zones, `zoned"..."` times, calendar periods like `1month`, and intervals are in the [language guide](https://github.com/david-andrew/dewy-lang/blob/master/docs/LANGUAGE.md#time-and-dates).

## Units

Physical quantities with checked dimensions come from `units`, as [the units chapter](../ch03/units.md) shows.

## Command-line programs

`import argparse` turns `main`'s `argv` into a typed record. You describe each argument once: its type, default and help text. Parsing, error messages for bad input and `--help` come with it.

<!-- dewy-example: {"mode": "run", "stdout": "HELLO, ADA\nHELLO, ADA\n", "args": ["ada", "shout=true", "times=2"]} -->
```dewy
import argparse

Args:type = [
    name = argparse.Positional<string>(help="who to greet")
    shout = argparse.Flag(help="use capitals")
    times = argparse.Named<int64>(default=1 help="repeat count")
]

main = (argv:array<string>) => {
    let args = argparse.parse(Args argv about="greet someone")
    loop i in 1..args.times {
        let text = "hello, {args.name}"
        printl(if args.shout text.upper else text)
    }
}
```

Bare words fill the positionals, `name=value` fills any argument by name, and `--shout` or `-s` turns a flag on.

## Files and paths

`p"notes.txt"` is a path. A path has the methods of Python's `pathlib`, and file operations give their failures back as values instead of raising. A trailing `;` discards a result you do not need.

<!-- dewy-example: {"mode": "run", "stdout": "one\ntwo\n\n"} -->
```dewy
main = ():>void => {
    let notes = p"notes.txt"
    notes.write_text("one\ntwo\n");
    match notes.read_text {
        text:string => printl(text)
        _ => printl"cannot read"
    }
    notes.unlink;
}
```

`run(program args)` starts a child process the same way and gives back its exit status. See [Errors as Values](../ch03/errors-as-values.md) for handling the failures.

## Networking, concurrency and more

`import net` gives sockets. Channels, parallel loops and tasks are covered in the [language guide](https://github.com/david-andrew/dewy-lang/blob/master/docs/LANGUAGE.md#parallel-cpu-work); [Effects](../ch03/effects.md) explains how the compiler tracks what a function may do.

## Game libraries

`lib/game/` and the programs in [`examples/`](https://github.com/david-andrew/dewy-lang/blob/master/examples/) cover windows, input, drawing, sprites, audio, curves, tile maps, 3D and GPU buffers. A small game is an `update` function and a `draw` function. `examples/paddle.dewy` is a complete one. Run it with `./tools/dewy examples/paddle.dewy` from a checkout.

The [current language guide](https://github.com/david-andrew/dewy-lang/blob/master/docs/LANGUAGE.md) has a section for each of these libraries.
