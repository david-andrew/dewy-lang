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

This should work on most linux distros with most common shells (`sh`, `bash`, `zsh`, `fish`). This script just attempts to add the lines below from the `Manual` section to your `.profile` or equivalent file, or your `.rc` file (e.g. `.bashrc`) if available.

If you don't have a `.rc` file, You will need to logout and log back in for changes to take effect. Otherwise, you can run `source ~/.rc` to apply changes, or open a new terminal.

### Manual

1. Add the following to your distribution/shell's corresponding `.profile` or `.rc` file:

   ```
   if [ -d "/home/user/path/to/dewy-lang" ]; then
     PATH="/home/user/path/to/dewy-lang:$PATH"
   fi
   ```

   > Note: Be sure to adjust the path in the command to match the current absolute path of **this** repo

   > Note: If modifying `.profile`, you must logout, and log back in for changes to take effect.
   > If modifying a `.rc` file (e.g. `.bashrc`), then either run `source path/to/.rc` to apply changes, or open a new terminal

## Try it out

> Note that the language parser is largely incomplete, and there are very many different syntaxes that will get trapped at breakpoints marking TODO, or cause exceptions for `NotImplementedError`

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

| Filename                                                        | status |
| --------------------------------------------------------------- | ------ |
| [hello.dewy](examples/hello.dewy)                               | [✓]    |
| [hello_func.dewy](examples/hello_func.dewy)                     | [✓]    |
| [hello_name.dewy](examples/hello_name.dewy)                     | [✓]    |
| [hello_loop.dewy](examples/hello_loop.dewy)                     | [✓]    |
| [anonymous_func.dewy](examples/anonymous_func.dewy)             | [✓]    |
| [if_else.dewy](examples/if_else.dewy)                           | [✓]    |
| [if_else_if.dewy](examples/if_else_if.dewy)                     | [✓]    |
| [dangling_else.dewy](examples/dangling_else.dewy)               | [✓]    |
| [if_tree.dewy](examples/if_tree.dewy)                           | [✓]    |
| [loop_in_iter.dewy](examples/loop_in_iter.dewy)                 | [✓]    |
| [loop_and_iters.dewy](examples/loop_and_iters.dewy)             | [✓]    |
| [enumerate_list.dewy](examples/enumerate_list.dewy)             | [✓]    |
| [loop_or_iters.dewy](examples/loop_or_iters.dewy)               | [✓]    |
| [nested_loop.dewy](examples/nested_loop.dewy)                   | [✓]    |
| [block_printing.dewy](examples/block_printing.dewy)             | [✓]    |
| [loop_iter_manual.dewy](examples/loop_iter_manual.dewy)         | [✗]    |
| [range_iter_test.dewy](examples/range_iter_test.dewy)           | [✗]    |
| [functions.dewy](examples/functions.dewy)                       | [✗]    |
| [unpack_test.dewy](examples/unpack_test.dewy)                   | [✗]    |
| [fizzbuzz-1.dewy](examples/fizzbuzz-1.dewy)                     | [✓]    |
| [fizzbuzz0.dewy](examples/fizzbuzz0.dewy)                       | [✗]    |
| [fizzbuzz1.dewy](examples/fizzbuzz1.dewy)                       | [✗]    |
| [random.dewy](examples/random.dewy)                             | [✗]    |
| [fast_inverse_sqrt.dewy](examples/fast_inverse_sqrt.dewy)       | [✗]    |
| [rule110.dewy](examples/rule110.dewy)                           | [✗]    |
| [dewy_syntax_examples.dewy](examples/dewy_syntax_examples.dewy) | [✗]    |
| [syntax.dewy](examples/syntax.dewy)                             | [✗]    |
| [tokenizer.dewy](examples/tokenizer.dewy)                       | [✗]    |

## Documentation

Currently out of date documentation is available at: https://david-andrew.github.io/dewy-lang/

## License

This project is dual-licensed under the MIT License and the Apache License 2.0. You may choose to use this project under the terms of either the MIT License or the Apache License 2.0. See the [LICENSE-MIT](LICENSE-MIT) and [LICENSE-APACHE](LICENSE-APACHE) files in this repository for the full text of the licenses.

## Contributing

Contributions to this project are accepted under the same dual-license terms as the project itself. By contributing, you agree to license your contributions under both the MIT License and the Apache License 2.0.
