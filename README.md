<p align="center">
  <img src="https://raw.githubusercontent.com/david-andrew/dewy-lang/master/assets/dewy_logo_128x128.png" alt="Dewy logo" />
</p>

# The Dewy Programming Language

Dewy is a general purpose programming language with a focus on engineering.

> **NOTE: Still very work in progress, and the docs (including this README) are frequently out of date!**

## Current Status

### dewy

The main compiler lives under [dewy/](dewy/)

### udewy

The micro subset, udewy, is largely feature complete and available under [udewy/](udewy/). Currently only supports linux x86_64.

A vscode extension for syntax highlighting is available at https://marketplace.visualstudio.com/items?itemName=RedFoxLabs.udewy

## Installation

Linux x86_64. This installs the `udewy` bootstrap compiler and the current Python-backed `dewy` compiler into `~/.dewy`:

```
curl -fsSL https://dewy-lang.org/install.sh | bash
```

The first `dewy` invocation checks for Python 3.12 or newer and caches the compatible interpreter path for later runs. You can then run a program with:

```
dewy path/to/my_script.dewy
```

From a checkout, the equivalent command is:

```
python -m dewy path/to/my_script.dewy
```

`udewy` programs can also be run with `python -m udewy` from a checkout.

## Examples

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
| [row_vs_col.dewy](examples/row_vs_col.dewy)                     | [✗]    |
| [tensors.dewy](examples/tensors.dewy)                           | [✗]    |
| [arrays.dewy](examples/arrays.dewy)                             | [✗]    |
| [objects.dewy](examples/objects.dewy)                           | [✓]    |
| [unpack_array.dewy](examples/unpack_array.dewy)                 | [✓]    |
| [unpack_dict.dewy](examples/unpack_dict.dewy)                   | [✓]    |
| [unpack_object.dewy](examples/unpack_object.dewy)               | [✗]    |
| [declare.dewy](examples/declare.dewy)                           | [✗]    |
| [loop_iter_manual.dewy](examples/loop_iter_manual.dewy)         | [✗]    |
| [range_iter_test.dewy](examples/range_iter_test.dewy)           | [✗]    |
| [functions.dewy](examples/functions.dewy)                       | [✓]    |
| [partial_functions.dewy](examples/partial_functions.dewy)       | [✓]    |
| [closure.dewy](examples/closure.dewy)                           | [✓]    |
| [function_signatures.dewy](examples/function_signatures.dewy)   | [✓]    |
| [opchains.dewy](examples/opchains.dewy)                         | [✓]    |
| [ops.dewy](examples/ops.dewy)                                   | [✗]    |
| [shebang.dewy](examples/shebang.dewy)                           | [✗]    |
| [fizzbuzz-1.dewy](examples/fizzbuzz-1.dewy)                     | [✓]    |
| [fizzbuzz0.dewy](examples/fizzbuzz0.dewy)                       | [✓]    |
| [fizzbuzz1.dewy](examples/fizzbuzz1.dewy)                       | [✗]    |
| [random.dewy](examples/random.dewy)                             | [✓]    |
| [primes.dewy](examples/primes.dewy)                             | [✓]    |
| [primes2.dewy](examples/primes2.dewy)                           | [✗]    |
| [mdbook_preprocessor.dewy](docs/plugins/src_to_iframe.dewy)     | [✗]    |
| [fast_inverse_sqrt.dewy](examples/fast_inverse_sqrt.dewy)       | [✗]    |
| [rule110.dewy](examples/rule110.dewy)                           | [✗]    |
| [dewy_syntax_examples.dewy](examples/dewy_syntax_examples.dewy) | [✗]    |
| [syntax.dewy](examples/syntax.dewy)                             | [✗]    |
| [tokenizer.dewy](examples/tokenizer.dewy)                       | [✗]    |

## Buzzwords

Just an (unsorted) collection of common buzzwords that apply to Dewy

- expression oriented
- statically compiled
- strongly typed
- type inference
- parametric polymorphism
- refinement types / liquid types
- effects system
- first-class types
- value semantics
- hybrid nominal-structural type system
- first-class functions
- function overloading
- array programming / broadcasting
- units of measure
- (mostly) automatic memory management, no GC
- ergonomic strings (extended grapheme clusters, interpolation, multilin, flexible delimiters)
- compiletime evaluation for metaprogramming
- juxtaposition (type-directed call, multiply, index)

## Documentation

The language website, learning guide, reference, examples, and µDewy playground are built from [`site/`](site/) and published at https://dewy-lang.org/.
