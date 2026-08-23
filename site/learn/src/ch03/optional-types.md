# Optional Types

`undefined` is a real value you can store and pass around. It is not `void`, and it is not a name you forgot to set.

An optional is `T | undefined`. Check with `is?` or `isnt?` before you use it as `T`. After the check, Dewy treats it as `T`:

```dewy
let answer:int64|undefined = find_answer()

if answer isnt? undefined {
    printl'{answer + 1}'
}

if answer is? int64 {
    printl'{answer + 1}'
}
```

`value is? T` asks whether the value actually is a `T`. `isnt?` is the other way.

## Where Optionals Come From

`in` assigns the next iterator value, or `undefined` when it is done, and returns whether it got something. See [Loops](loops.md).

Combine iterators with `or` and one side can run out while the loop keeps going. That side is `T | undefined`:

```dewy
loop short_item in short_items or long_item in long_items
{
    if short_item isnt? undefined {
        process(short_item)
    }
    process(long_item)
}
```

A function can return an optional directly:

```dewy
let choose = (flag:bool):>int64|undefined =>
    if flag 40 else undefined
```
