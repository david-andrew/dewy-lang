# Operators

Dewy is a 100% expression-based language, meaning everything is formed from small pieces combined together with operators. Dewy has 3 types of operators:
- unary prefix: come before the expression
- binary infix: come between two expressions
- unary postfix: come after the expression

## Binary Operators

(TODO: this is missing several operators, and may have some extra ones that are no longer planned)

**Basic Math Operations**
- `+` plus
- `-` minus
- `*` multiply
- `/` divide
- `%` modulus
- `^` exponent

**logical and bitwise operations**
> Note: these are logical if both operands are boolean, otherwise they are bitwise and operate on as many bits as the size of the largest operand

- `and` both are true
- `or` either are true
- `xor` exactly one is true
- `not` invert (unary)
- `nand` either is false
- `nor` both are false
- `xnor` both are false or both are true

**bit-shift operations**
- `<<!` rotate left through carry bit
- `!>>` rotate right through carry bit
- `<<<` rotate left no carry bit
- `>>>` rotate right no carry bit
- `<<` shift left (arithmetic and logical are the same for left-shift) 
- `>>` shift right (arithmetic vs logical determined by whether signed or unsigned)

**boolean returning operations**
- `=?` equal<!-- - `not?` not equal -->
- `>?` greater than
- `>=?` greater than or equal
- `<?` less than
- `<=?` less than or equal
- `in?` is a member of

<!-- **Special Operators**
- `<=>` spaceship (three-way comparison) -->

**colon operator**
- `:` apply a type annotation

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
- `:=` (walrus operator) same as normal assignment operator, but also returns the righthand side as an expression available for use.

**Juxtaposition**

(TODO: explain how juxtaposition works)

## Unary Prefix Operators
(TODO: prefix operators)

## Unary Postfix Operators
(TODO: postfix operators)

## In-place Assignment

any of the logical/bitwise operators, as well as the boolean returning operators can be preceeded by `not` which will then cause the inverse of the operation to be returned. e.g. `not and` is equivalent to `nand`, `not <?` is equivalent to `>=?`, etc.

most binary operators can be appended with an `=` sign to make them into an assignment
e.g. 

```
a += 5  //is equivalent to a = a + 5
a <?= 5  //is equivalent to a = a <? 5
a !>>= 5  //is equivalent to a = a !>> 5
a xor= false  //is equivalent to a = a xor false
```

(TODO: This should also probably be able to be combined with element-wise/vectorized `.` operations where each element in the list is updated according to the operation (can be done in parallel))

## Elementwise Operations

the elementwise operator `.` can be prepended to most binary operators to make it be performed on each element in a array or sequence 
e.g. 

```
//find the prime factors of 20
a = [2 3 5 7 11 13 17 19]  //primes up to 20
mods = 20 .% a  //returns [0 2 0 6 9 7 3 1]
is_factor = mods .=? 0 //returns [true false true false false false false]
p_factors = a[is_factor] //returns [2 5]

//above in a single line
p_factors = [2 3 5 7 11 13 17 19][20 .% [2 3 5 7 11 13 17 19] .=? 0]

//though it's probably cleaner in 2 lines
primes = [2 3 5 7 11 13 17 19]
p_factors = primes[20 .% primes .=? 0]
```

This works if either the either first operand is a list, or the second is a list, or both are lists with the exact same shape


## Precedence

Every operator has a precedence level, and an associativity. The precedence level determines the order in which operators in a compound expression are evaluated. Associativity determines the order of evaluation when multiple operators of the same precedence level are present in a compound expression. Associativity can be:
- left-to-right
- right-to-left
- prefix
- postfix
- none (typically these expressions generate a single node in the AST)
- fail (i.e. the expression is invalid if multiple operators of the same precedence level are present)

(TODO: some way of populating this table with the current full precedence table in the code)


(TODO: this table is missing several operators)

| Precedence | Symbol | Name | Associativity |
| --- | --- | --- | --- |
| 14 | `@` | reference | prefix |
| 13 | `.`<br>juxtapose<br>juxtapose | access<br>jux-call<br>jux-index | left |
| 12 | `^` | power | right |
| 11 | juxtapose | jux-multiply | left |
| 10 | `*`<br>`/`<br>`%` | multiply<br>divide<br>modulus | left |
| 9 | `+`<br>`-` | add<br>subtract | left |
| 8 | `<<`<br>`>>`<br>`<<<`<br>`>>>`<br>`<<!`<br>`!>>` | left shift<br>right shift<br>rotate right no carry<br>rotate left no carry<br>rotate left with carry<br>rotate right with carry | left
| # | `in` | in | fail |
| 7 | `=?`<br>`>?`<br>`<?`<br>`>=?`<br>`<=?` | equal<br>greater than<br>less than<br>greater than or equal<br>less than or equal | left |
| 6 | `and`<br>`nand`<br>`&` | and<br>nand<br>and | left |
| 5 | `xor`<br>`xnor` | xor<br>xnor | left |
| 4 | `or`<br>`nor`<br>\| | or<br>nor<br>or | left |
| 3 | `comma` | comma | none |
| # | juxtapose | jux-range | none |
| 2 | `=>` | function arrow | right |
| 1 | `=` | bind | fail |
| 0 | `else` | flow alternate | none |
| -1 | space | space | left |
| TBD |  `as`     | as          |     TBD       |
| TBD |`transmute`| transmute   |     TBD       |
| TBD |   \|>     | pipe        |     TBD       |
| TBD |   <\|     | reverse pipe|     TBD       |
| TBD |   `->`    | right-pointer |   TBD       |
| TBD |   `<->`   | bi-pointer |      TBD       |
| TBD |   `<-`    | left-pointer |    TBD       |
| TBD |   `:`     | type annotation | TBD       |


multi-operators e.g. `100^/2` for sqrt, or `5+-1`, etc. have a precedence at the level of the first operator in the chain (i.e. all following operators have no effect on the precedence).
Also any instances of elementwise operators (e.g. `.+` `.=` `.xor` etc.) are at the level of precedence as the operator they're attached to. Assignment operators on the other hand are all at the same level, regardless of the type of operator they're attached to (e.g. `+=` `<?=` `<<=` `nand=` etc.)