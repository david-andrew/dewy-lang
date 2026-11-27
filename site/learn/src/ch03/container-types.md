# Containers

An array holds values of one type, written between brackets and separated by spaces. A loop in brackets builds a new array, and methods such as `sorted`, `map` and `filter` cover the usual transformations.

<!-- dewy-example: {"mode": "run", "stdout": "[40 42]\n[3 2 1]\n6\n"} -->
```dewy
let values = [20 21]
let doubled = [loop value in values value * 2]
printl(doubled)
printl([1 3 2].sorted(reverse=true))

let xs = [1 2 3]
xs.push(0)
printl(xs.length + 2)
```

A dictionary maps keys to values with `->`. Reading a key that might be missing uses `get` with a fallback; once a key is known to be present, `d[k]` needs no check:

<!-- dewy-example: {"mode": "run", "stdout": "[\"apple\" -> 2 \"pear\" -> 1]\n0\n"} -->
```dewy
let basket:dict<string int> = []
loop fruit in ["apple" "pear" "apple"] {
    if fruit not in? basket basket[fruit] = 0
    basket[fruit] += 1
}
printl(basket)
printl(basket.get("plum") ?? 0)
```

Sets, fixed-length arrays, numeric arrays with shapes, and GPU arrays build on the same forms.

The [reference](/reference/arrays-and-containers.html) has the complete rules.
