## unicode escape that doesn't consume adjacent number characters
* if you for some reason needed to do a unicode escape followed by a character that happens to be a hex digit, you could do:
`\u##{}#`, where the empty block {} breaks the hex digit sequence. Also you could do `\u##\#` (preferred style)

## juxtapose can have different precedence depending on the operand types
This is mainly for when a jux is next to a power. Juxtapose can mean either multiplication (with slightly higher precedence than * multiplication), or function call. The precedence goes like this:
```
[HIGHEST]

...
<jux call>
^
<jux mul>
* / // tdiv rdiv fdiv cdiv mod rem
<jux range> //note jux range can be converted to an explicit operator since it will always appear next to a `..` token
...

[LOWEST]
```

The specific jux used depends on the left and right arguments. For example:
```
result = sin(x)^2 + cos(x)^2
```

`sin` and `cos` are normally math functions, so the jux has higher precedence than the power (i.e. `(sin(x))^2 + (cos(x))^2`). But with an almost identical expression, we can have the precedence be reversed:
```
s = 10 c = 20
result = s(x)^2 + c(x)^2
```

Because `s` and `c` are numbers, the jux is interpreted as multiplication, and thus power has a higher precedence (i.e. `s(x^2) + c(x^2)`).

In fact you can even overwrite the sin/cos functions and get the second behavior:
```
sin = 10 cos = 20
result = sin(x)^2 + cos(x)^2
```

The particular precedence chosen is based on the arguments. If the left argument is callable, then the jux-call operator will be used. else if it is a numeric expression, then the jux-mul operator will be used. **If possible, this will be determined at compile-time, otherwise it will be determined at runtime**.


## Ambiguous Jux Parses
This is a corollary to jux representing two operators of different precedence. Basically the way that the different precedence levels will be handled is that at parse time, the type of the left operand of the jux will be checked to see if it is a function, indicating the higher precedence jux-call operator, or if it is numeric, indicating the lower precedence jux-mul operator.

Given this, it should be possible to construct a parse where if it is interpreted as jux-call, then the left operand is not a function, but if it is interpreted as jux-mul, then the left operand is not interpreted as a number. Though I seem to be having trouble constructing an example
```
a^(f)(x)^b
```

To get this to be a problem, you'd need to construct something that looks like a function when interpreting the operator as jux-mul, but looks like a number when the operator is jux-call. I'm not gonna worry for now

## Juxtapose call is right associative while juxtapose multiply is left associative
```
//functions f and g
f(g)(x)  // f(g(x))

// numbers a b and c
a(b)(c) // (a*b)*c
```

TBD if this can cause parse ambiguity


# preset constants
## unmodifiable constants
- `pi`
- `inf`

## modifiable constants
- `i`, `j`, `k` //should have a warning when trying to use them with numbers if they've been redefined
- all language-defined units, e.g. `kg`, `m`, `s`, `N`, `Pa`, etc.
    - for user defined constants, it will be up to the user if they want them to be modifiable, shadowable, or permanent


## The branches of chained flow control (if/loop) share scope
this mainly means that the conditions of each of the branches can share variables

```
if (a=10 a>?b) {...}
else if a>?c {...} //a is the same a created in first clause
```

## simple `count` implementation
the dewy implementation for the `count` iterator is literally just
```
count = () => 0..
```
