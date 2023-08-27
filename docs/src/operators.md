# Operators

Dewy is a 100% expression-based language, meaning operators are its bread and butter. Dewy has 3 types of operators:
- prefix: come before the expression
- infix: come between two expressions
- postfix: come after the expression

Additionally every operator has a precedence level, and an associativity. The precedence level determines the order in which operators in a compound expression are evaluated. Associativity determines the order of evaluation when multiple operators of the same precedence level are present in a compound expression. Associativity can be:
- left-to-right
- right-to-left
- prefix
- postfix
- none (typically these expressions generate a single node in the AST)
- fail (i.e. the expression is invalid if multiple operators of the same precedence level are present)

(TODO: some way of populating this table with the current full precedence table in the code)


(TODO: this table is missing several operators)

| Operator  | Precedence | Associativity |    Name     |
|-----------|------------|---------------|-------------|
|    `@`    |     15     |     prefix    | reference   | 
|    `.`    |     14     |     left      | access      | 
| Jux-call  |     14     |     left      | jux call    | 
| Jux-index |     14     |     left      | jux index   | 
|   `^`     |     13     |     right     | power       | 
| Jux-mul   |     12     |     left      | jux mul     | 
|   `*`     |     11     |     left      | multiply    | 
|   `/`     |     11     |     left      | divide      | 
|   `%`     |     11     |     left      | modulus     | 
|   `+`     |     10     |     left      | add         | 
|   `-`     |     10     |     left      | subtract    | 
|   `<<`    |     9      |     left      | left shift  | 
|   `>>`    |     9      |     left      | right shift | 
|   `>>>`   |     9      |     left      | rotate left no carry | 
|   `<<<`   |     9      |     left      | rotate right no carry| 
|   `<<!`   |     9      |     left      | rotate left with carry | 
|   `!>>`   |     9      |     left      | rotate right with carry | 
|   `,`     |     8      |     none      | comma       | 
| Jux-range |     7      |     left      | jux range   | 
|   `>?`    |     6      |     left      | greater than| 
|   `<?`    |     6      |     left      | less than   | 
|   `>=?`   |     6      |     left      | greater than or equal | 
|   `<=?`   |     6      |     left      | less than or equal | 
|   `=?`    |     6      |     left      | equal       | 
|   `and`   |     5      |     left      | and         | 
|   `nand`  |     5      |     left      | nand        | 
|   `&`     |     5      |     left      | and         | 
|   `xor`   |     4      |     left      | xor         | 
|   `xnor`  |     4      |     left      | xnor        | 
|   `or`    |     3      |     left      | or          | 
|   `nor`   |     3      |     left      | nor         | 
|   \|      |     3      |     left      | or          | 
|   `=>`    |     2      |     right     | function    | 
|   `=`     |     1      |     fail      | bind        | 
|   `else`  |     0      |     none      | flow alternate |
|   `;`     |     -1     |     postfix   | semicolon   |
|  space    |     -2     |     left      | space       |
|  `in`     |    TBD     |     TBD       | in          |
|  `as`     |    TBD     |     TBD       | as          |
|`transmute`|    TBD     |     TBD       | transmute   |
|   \|>     |    TBD     |     TBD       | pipe        |
|   <\|     |    TBD     |     TBD       | reverse pipe|
|   `->`    |    TBD     |     TBD       | right-pointer |
|   `<->`   |    TBD     |     TBD       | bi-pointer |
|   `<-`    |    TBD     |     TBD       | left-pointer |
|   `:`     |    TBD     |     TBD       | type annotation |



**Basic Math Operations**
- `+` plus
- `-` minus
- `*` multiply
- `/` divide
- `%` modulus
- `^` exponent

**logical and bitwise operations**
(note that these are logical if both operands are boolean, otherwise they are bitwise and operate on as many bits as the size of the largest operand)
- `and` both are true
- `or` either are true
- `xor` exactly one is true
- `not` invert (unary)
- `nand` either is false
- `nor` both are false
- `xnor` both are false or both are true

**bit-shift operations**
- `<<<!` rotate left through carry bit
- `!>>>` rotate right through carry bit
- `<<<` rotate left no carry bit
- `>>>` rotate right no carry bit
- `<<` shift left (arithmetic and logical are the same for left-shift) 
- `>>` shift right (arithmetic vs logical determined by whether signed or unsigned)

**boolean returning operations**
- `=?` equal
- `not?` not equal
- `>?` greater than
- `>=?` greater than or equal
- `<?` less than
- `<=?` less than or equal
- `in?` is a member of

**Special Operators**
- `<=>` spaceship (three-way comparison)

**colon operator** or **list creator operator**
- `:` creates a list/sequence

**dictionary pointers**
- `->` indicates the left expression points to the right expression in the dictionary
- `<-` reverses the order, making the right expression the key, and the left the value
- `<->` indicates that left is inserted as a key that points to right, and right is inserted as a key that points to left

**Function pointer**
- `=>` used for declaring a function literal

**handle operator**
- `@` return a handle to the function or variable
- `@?` (probably) check if two references are point to the same thing
 
**Assignment operators**
- `=` binds the righthand expression to the lefthand identifier as a statement (i.e. nothing is returned)
- `:=` (walrus operator) same as normal assignment operator, but also returns the righthand side as an expression available for use


## Notes

any of the logical/bitwise operators, as well as the boolean returning operators can be preceeded by `not` which will then cause the inverse of the operation to be returned. e.g. `not and` is equivalent to `nand`, `not <?` is equivalent to `>=?`, etc.

any of these operations can be appended with an `=` sign to make them into an assignment (this probably excludes `@` and `!` and any other unary operators)
e.g. 

```
a += 5  //is equivalent to a = a + 5
a <?= 5  //is equivalent to a = a <? 5
a !>>>= 5  //is equivalent to a = a !>>> 5
a xor= false  //is equivalent to a = a xor false
```

Can the `=` sign be (optionally) separated from the operation? e.g. `+=` is equivalent to `+ =`, `xor=` is equivalent to `xor =`, etc. I think it should be allowed in this case, so long as the first operator is in a single piece

This should also probably work with element-wise operations where each element in the list is updated according to the operation (can be done in parallel)

the elementwise operator `.` can be prepended to any operation to make it be performed on each element in a vector/matrix/tensor/etc. 
e.g. 

```
//find the prime factors of 20
a = [2 3 5 7 11 13 17 19]  //primes up to 20
mods = 20 .% a  //returns [0 2 0 6 9 7 3 1]
is_factor = mods .=? 0 //returns [true false true false false false false]
p_factors = a[is_factor] //returns [2 5]

//above in a single line
p_factors = [2 3 5 7 11 13 17 19][20 .% [2 3 5 7 11 13 17 19] =? 0]

//though it's probably cleaner in 2 lines
primes = [2 3 5 7 11 13 17 19]
p_factors = primes[20 .% primes =? 0]
```

This works if either the either first operand is a list, or the second is a list, or both are lists with the exact same shape


The current precedence levels for the operations are as follows:

```
precedence_levels = 
[
    0 -> [ '=' ]  //assignmnent (also += <?= xor= etc.)
    1 -> [ 'and' 'or' 'xor' 'not' 'nand' 'nor' 'xnor' ]  // 'not' might actually be inserted in between 7 and 8 as it's a unary operator
    2 -> [ '=?' 'not?' '>?' '>=?' '<?' '<=?' 'in?' ]
    3 -> [ '!>>>' '<<<!' '>>>' '<<<' '>>' '<<' ]
    4 -> [ '+' '-' ]
    5 -> [ '*' '/' '%' ]
    6 -> [ 'm' 'd' ]  //unit versions of divide (d) and multiply (m), bind more tightly than normal arithmetic. You can't actually use these in the language
    7 -> [ '^' ]
    8 -> [ ':' ]  //list maker e.g. 1:10. This probably should be much lower, i.e. between 1 and 2, or 2 and 3
    9 -> [ '!' ]
    10 -> [ 'a.b' 'a()' 'a[]' ]  //attribute access e.g. some_obj.value
    11 -> [ '@' ]  //11 might actually swap with 10
    12 -> [ 'if' ]  //ternary if
    13 -> [ '()' ]  //parenthesis groupings
    14 -> [ '{}' ]  //block grouping
]
```

If we add a three-way comparison operator, it goes between levels 0 and 1. Also any multi-operators e.g. `100^/2` for sqrt, or `5+-1`, etc. have a precedence at the level of the first operator in the chain (i.e. all following operators have no effect on the precedence).
Also any instances of elementwise operators (e.g. `.+` `.=` `.xor` etc.) are at the level of precedence as the operator they're attached to. Assignment operators on the other hand are all at the same level, regardless of the type of operator they're attached to (e.g. `+=` `<?=` `<<=` `nand=` etc.)