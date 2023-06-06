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
/ * %
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



# preset constants
## unmodifiable constants
- `pi`
- `inf`

## modifiable constants
- `i`, `j`, `k` //should have a warning when trying to use them with numbers if they've been redefined
