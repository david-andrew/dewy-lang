# The Standard Library

The compiler finds its matching libraries beside the standalone executable. `dewy-core --print-lib` prints the active library directory. In a checkout, `lib/` holds containers, platform services and game libraries.

<!-- dewy-example: {"mode": "run", "stdout": "42\n"} -->
```dewy
from units import m
let distance = 42m
printl(distance/m)
```

The second is in the prelude; other physical units come from `units`. Browse the [library source](https://github.com/david-andrew/dewy-lang/blob/master/lib/) and the [current language guide](https://github.com/david-andrew/dewy-lang/blob/master/docs/LANGUAGE.md). Host services have target-specific constraints; native coverage does not imply browser support.
