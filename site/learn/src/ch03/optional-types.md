# Optional Values and Narrowing

Dewy has no `null`. A value that may be missing has a union type with `none`, such as `int | none`, written `int?` for short. Before using it as an `int`, the code has to rule out `none`.

<!-- dewy-example: {"mode": "run", "stdout": "found at 1\nnot found\n"} -->
```dewy
position_of = (xs:array<string> target:string):>int? => {
    loop i in 0.. and x in xs if x =? target return i
    none
}

names = ["ada" "grace" "alan"]
loop who in ["grace" "linus"] {
    let at = position_of(names who)
    if at is? int printl"found at {at}" else printl"not found"
}
```

Inside the `if`, `at` is narrowed to `int`. Three other forms come up constantly:

<!-- dewy-example: {"mode": "run", "stdout": "0\n4\nnobody\n"} -->
```dewy
ages = ["ada" -> 36 "alan" -> 41]
printl(ages.get("grace") ?? 0)              # a default with ??

names = ["ada" "grace" "alan"]
let last = names.get(2)
if last isnt? none printl(last.length)      # narrowed to string

who = [3 1 4].get(9)
printl(match who { n:int => "{n}" <none> => "nobody" })
```

`xs.get(i)` and `d.get(k)` are how you read a position or key that might not exist: they give an optional instead of crashing.

The [reference](/reference/types-and-conversions.html) has the complete rules.
