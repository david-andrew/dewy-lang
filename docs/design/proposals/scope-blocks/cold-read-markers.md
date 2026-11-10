# Cold reads 17-18: scope-block markers (three fresh readers, a, b, c)

Question (a): does the brace run as part of the surrounding function (return leaves it)? (b): is the `with` name created by the call?

| Spelling | 17 (a) | 18 (a) | (b) | Verdict |
|---|---|---|---|---|
| `do { }` | no / yes / no | yes 3 / yes 3 / no 2 | - | fail (3 of 6 callback) |
| `inline { }` | - | yes 4 / yes 4 / yes 3 | - | pass, best |
| `here { }` | - | yes 4 / yes 4 / yes 2 | - | pass |
| `within { }` | - | yes 4 / yes 3 / yes 2 | - | pass, but clashes with `within` (deadline) |
| `: { }` | - | yes / yes 3 / yes 3 | - | pass, low |
| `with group { }` | yes / yes / no | yes / no / no | created 3/3 | (a) weak; (b) pass |
| `inline with group { }` | - | yes / yes 4 / yes 3 | created 3/3 | pass |
| `with (ctrl_c group) { }` | yes / yes / no | - | created 2/3 | weak |
| `scope(:>R)` param | - / yes / callback | - | - | weak; hover/diagnostic carries it |
