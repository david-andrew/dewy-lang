# The Dewy Programming Language
Dewy is a general purpose programming language with a focus on engineering.

**Still very work in progress**

## Installation

### Dependancies
For now, the only dependancy is **Python >= 3.11** with an optional dependancy on `rich` for rich printing/errors (`pip install rich`)

Later dependancies will probably include `clang`/`llvm`

### Automatic

```
python install.py
```

This should work on most linux distros with most common shells (`sh`, `bash`, `zsh`, `fish`). This script just attempts to add the lines below from the `Manual` section to your `.profile` or equivalent file.

You will need to logout and log back in for changes to take effect.

### Manual
1. Add the following to your distribution/shell's corresponding `.profile` file: 

    ```
    if [ -d "/home/user/path/to/dewy-compiler-compiler" ]; then
      PATH="/home/user/path/to/dewy-compiler-compiler:$PATH"
    fi
    ```

    **Note: Be sure to adjust the command to match the current absolute path of this repo**

1. Then logout, and log back in for changes to take effect


## Try it out
Note that the language parser is largely incomplete, and there are very many different syntaxes that will get trapped at breakpoints marking TODO, or cause exceptions for `NotImplementedError`

If you completed the install steps, you can simply run:
```
dewy my_script.dewy
```

otherwise you can run the python script directly
```
cd src/compiler
python compiler.py ../path/to/my_script.dewy
```

### Examples
Several example programs are available in [examples/](examples/). Here is a breakdown of which ones work with the current progress:

| Filename                  |  status  |
|---------------------------|----------|
| hello.dewy                |    [✓]   |
| hello_func.dewy           |    [✓]   |
| hello_loop.dewy           |    [✓]   |
| hello_name.dewy           |    [✓]   |
| anonymous_func.dewy       |    [✓]   |
| if_else.dewy              |    [✓]   |
| if_else_if.dewy           |    [✓]   |
| loop_in_iter.dewy         |    [✗]   |
| loop_iter_manual.dewy     |    [✗]   |
| nested_loop.dewy          |    [✗]   |
| range_iter_test.dewy      |    [✗]   |
| block_printing.dewy       |    [✗]   |
| unpack_test.dewy          |    [✗]   |
| rule110.dewy              |    [✗]   |
| dewy_syntax_examples.dewy |    [✗]   |
| fast_inverse_sqrt.dewy    |    [✗]   |
| fizzbuzz0.dewy            |    [✗]   |
| fizzbuzz1.dewy            |    [✗]   |
| syntax.dewy               |    [✗]   |
| tokenizer.dewy            |    [✗]   |




## Documentation
Currently out of date documentation is available at: https://david-andrew.github.io/dewy-compiler-compiler/