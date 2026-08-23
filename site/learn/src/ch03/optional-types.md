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

You can also narrow by returning or exiting

```dewy
# narrow to int64 or quit
if answer is? undefined { exit(1) }

# can use without guard
printl'answer is {answer}'
```

`value is? T` asks whether the value actually is a `T`. `isnt?` is the other way.

## Where Optionals Come From

Optionals can come from any source that wants to represent a value or nothing. Functions can return them, you can construct them directly, and certain expressions will naturally generate them.

```dewy
let myoption:string|undefined = if value =? 42
    'life, the universe, and everything'
else
    undefined
```

Iterators are a common example that `undefined` might come up. `in` assigns the next iterator value, or `undefined` when it is done, and returns whether it got something. See [Loops](loops.md).

Combine iterators with `or` and one side can run out while the loop keeps going. That side is `T | undefined`:

```dewy
short_list = [1 2 3]
long_list = ['this' 'is' 'a' 'long' 'list' 'of' 'items']
loop short in short_list or long in long_list
{
    if short_item isnt? undefined {
        process(short_item)
    }
    process(long_item)
}
```

The iterations will have the following values

```
0: short=1         long='this'
1: short=2         long='is'
2: short=3         long='a'
3: short=undefined long='long'
4: short=undefined long='list'
5: short=undefined long='of'
6: short=undefined long='items'
```

Lastly, a function can return an optional directly:

```dewy
let choose = (flag:bool):>int64|undefined =>
    if flag 40 else undefined
```
