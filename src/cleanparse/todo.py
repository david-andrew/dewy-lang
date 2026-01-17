"""
# parsing pipeline steps
## tokenizer
initial pass, simplest tokens

## t2
make compound tokens like string, block, float, etc.

## juxtaposer
invert whitespace for juxtapose (does this maybe go after flower?)

## chainer/flower
identify expression chains (so can do all <keyword><expr><expr>... style expressions (e.g. loops, if else, return, etc.))
## pratt/shunt parse
generally ignore chains (which are glorified list[Token]). first pass at parsing using my looped shunting algorithm

## p2
tbd next parsing ## passes, etc.

## typer
type checking. probably get rid of all ambiguous nodes at this point either by determining correct path via types or erroring
should have final complete sharable AST trees which can be passed to backends

## AST optim
tbd for later

## codegen
given AST, produce output in the target backend




[tasks]
[x] remove FlowArm in favor of KeywordExpr
[x] get pathological test working
[ ] remove left prefix checking since we have chains now
[ ] full error reporting in t2 at indicated locations
[ ] full error reporting in p0 at indicated locations


[ ] handling ambiguous parses:
    - use existing Ambiguous: list[AST] struct
    - make a proper struct/dataclass for Reduction()
    - when going into the shunt pass, for a in associativity, cache those inputs if they produced a reduction (be careful to compare on identity rather than equality so that we only cache the actual right thing)
    - the list of items should actually be possible to be a multi-list of items, with each sub list being one of the possible parses
        - perhaps it is a set so we get auto-dedup, but maybe we manually have to track dedup
    - parent context receives a list[AST] or multilist[AST], and if it was a multilist, we spawn make an Ambiguous node out of the reciever, containing the receiver containing one of each of the inner versions
        - e.g. block.inner -> list[list[AST]]. for candidate:list[AST] in ambiguous_parsed_inners: Ambiguous.append(Block[candidate])
    - for convenience, probably package up aspects of the shunt pass as separate functions, so its easier to deal with ambiguous vs regular case
    - potentially can fold in some of the other ambiguous stuff (e.g. if multiple reductions occur? (but only we couldn't determine))

[ ] when printing error report, take whole span of text being printed out, and dedent as much as possible (e.g. if we were just looking at something very nested and nothing surrounding it, we don't need all the indentation)
[x] would be nice if associativity.flat could indicate a max number of the operator allowed (e.g. 2 for `..`, inf for `,`)
    ---> tbd because might be nicer just to handle it in p1
[x] A ` B should disambiguate based on the slight higher precedence of prefix over postfix. not sure how to handle... perhaps reductions could indicate a precedence?
[x] `;` cannot participate in binops, prefix ops, or postfix ops (except for semicolon juxtapose)
[-] overhaul how juxtapose tokens are determined. basically they can be next to operators, so long as that op is part of a chain
[x] actually just semicolon is special. if it is touching anything to the left, it gets semicolon juxtapose
    [x] semicolon cannot have juxtapose to right
    [x] semicolon juxtapose should be allowed if touching anything to the left
    [x] .. also can juxtapose anything left or right regardless of if it is an operator or not
[x] need backtick disambiguation. suspect when checking if could be postfix op, need to check that backtick has something to connect to
[x] replace `#` with `$` and then make comments be `#` and `#{}#`
[x] add ${} interpolation strings (consider reworking strings in t0 since there's a lot of similar patterns. maybe make a string token factory)

[Tasks]
[x] split invert_whitespace into remove_whitespace and insert_juxtapose
[x] op function literals
[x] make @ just a regular prefix op instead of consuming it in the tokenizer (so we can @ fn literals, and opfn e.g. cycleleft = @(`)(dir='left'))
[.] operator precedence parse
    [x] primary impl
    [x] recursing into inners
    simplify/clean up?


operator precedence parse test

% all commas combine in a single step as a single flat comma operator
1,2,3,4+5/6*7,8+9,0
basically when counting backwards, we see 1,2 and as we're reducing it, we see if after 2 is a comma and something that came to that comma, and include it if so, and continue pulling the right most comma+ast in until there are no more commas. If there is a comma, and the thing next to it did not come to it, we can't do this flat comma yet!



[x] implement parametric escapes in t1
[-] build opchains in t2/postok
[x] bundle conditionals in t2
[ ] initial parse pass with pratt parser
[x] make int literal only support up to base 16
    [ ] write out why have both based strings and based arrays. (BLUF: based arrays are just normal arrays you sequence whatever you want, no bit packing/etc. strings are for fixed chunks (e.g. 2 hex digits for bytes, 8 bits for byte, etc.))




[ ] flag for spans where if set to true, and they would break a line, keep on the initial line and extend to end

[ ] error report for TODOs
[x] deduplicate effort in identifying if error case is true. basically in the token eat function, break out sub functions that are called by eat, and can also be called by the error checking function
    ---> e.g. invalid_width_hex_escape has a lot of shared logic that could be factored into helpers in StringEscape's (static) methods

[ ] error reporting improvement ideas:
    [ ] consider allowing raising errors from within eat functions, so then we can throw inside tokenize() and print any stack remaining errors?
        ---> or potentially Context(ABC) gets a member that eat functions can push to errors to
    [ ] consider ability to eat broken tokens, so we can continue tokenizing, and then report everything at the end


[ ] errors for no token matches, check prev and next context cases if they could have matched
[ ] report printout support overlapping spans: so long as they can be cleanly divided by top and bottom of line
    - needed for the >> in type param context error (and potentially other cases)
[x] report printout support specifying color index for specific pointers (and ideally try to make sure the same color isn't used adjacently)
    [x] make an example that forces color switching for a pointer of the same color_id (i.e. force a given token to touch at least 5 other token colors, where they all also touch enough other colors)
[x] tokenize rest-of-file strings
[x] tokenize integers
[x] error case in heredoc string opener unclosed delimiter case
------ tokenizer features ------
[x] #"EOF" for heredoc strings `#"`, <delimiter>, `"`, <string body>, <delimiter>
    - #r"EOF" for raw heredoc strings
    - delimiter can be any identifier character as well as any symbol character except for quotes `"`, `'`
[x] fix string escapes to include unicode and hex escapes correctly
    - `\x{...}` where inside interpolation is either a sequence of digits (assumed to be hex unless otherwise prefixed), or any other arbitrary expression that evaluates to an integer
    - `\u{...}` where inside interpolation is either a sequence of digits (assumed to be hex unless otherwise prefixed), or any other arbitrary expression that evaluates to an integer
[ ] select larger list of (math) symbols to include
[ ] symbol normalization e.g. μ vs µ  (greek mu vs micro sign), subscripts and superscripts, etc.

------ slightly broader scope ------
[ ] next tokenization step for hello world: insert juxtapose
[ ] finish whole parsing process for hello world happy path



------ misc ------
[ ] TODO manager: (likely to use alstr/todo-to-issue-action )
    - every comment starting with TODO receives a unique ID (git push hooks add them)
    - every new TODO gets a git issue created for it
    - every TODO with an ID that is removed closes the git issue
- not handled by alstr/todo-to-issue-action, but would be ideal if LLM could write the issue description (rather than just quoting the comment)
    
"""



"""
μ vs µ  (greek mu vs micro sign)

†‡


[operators to potentially include]
U+2200
∀
For All

U+2201
∁
Complement

U+2202
∂
Partial Differential

U+2203
∃
There Exists

U+2204
∄
There Does Not Exist

U+2205
∅
Empty Set

U+2206
∆
Increment

U+2207
∇
Nabla

U+2208
∈
Element Of

U+2209
∉
Not An Element Of

U+220A
∊
Small Element Of

U+220B
∋
Contains as Member

U+220C
∌
Does Not Contain as Member

U+220D
∍
Small Contains as Member

U+220E
∎
End of Proof

U+220F
∏
N-Ary Product

U+2210
∐
N-Ary Coproduct

U+2211
∑
N-Ary Summation

U+2212
−
Minus Sign

U+2213
∓
Minus-or-Plus Sign

U+2214
∔
Dot Plus

U+2215
∕
Division Slash

U+2216
∖
Set Minus

U+2217
∗
Asterisk Operator

U+2218
∘
Ring Operator

U+2219
∙
Bullet Operator

U+221A
√
Square Root

U+221B
∛
Cube Root

U+221C
∜
Fourth Root

U+221D
∝
Proportional To

U+221E
∞
Infinity

U+221F
∟
Right Angle

U+2220
∠
Angle

U+2221
∡
Measured Angle

U+2222
∢
Spherical Angle

U+2223
∣
Divides

U+2224
∤
Does Not Divide

U+2225
∥
Parallel To

U+2226
∦
Not Parallel To

U+2227
∧
Logical And

U+2228
∨
Logical Or

U+2229
∩
Intersection

U+222A
∪
Union

U+222B
∫
Integral

U+222C
∬
Double Integral

U+222D
∭
Triple Integral

U+222E
∮
Contour Integral

U+222F
∯
Surface Integral

U+2230
∰
Volume Integral

U+2231
∱
Clockwise Integral

U+2232
∲
Clockwise Contour Integral

U+2233
∳
Anticlockwise Contour Integral

U+2234
∴
Therefore

U+2235
∵
Because

U+2236
∶
Ratio

U+2237
∷
Proportion

U+2238
∸
Dot Minus

U+2239
∹
Excess

U+223A
∺
Geometric Proportion

U+223B
∻
Homothetic

U+223C
∼
Tilde Operator

U+223D
∽
Reversed Tilde

U+223E
∾
Inverted Lazy S

U+223F
∿
Sine Wave

U+2240
≀
Wreath Product

U+2241
≁
Not Tilde

U+2242
≂
Minus Tilde

U+2243
≃
Asymptotically Equal To

U+2244
≄
Not Asymptotically Equal To

U+2245
≅
Approximately Equal To

U+2246
≆
Approximately But Not Actually Equal To

U+2247
≇
Neither Approximately Nor Actually Equal To

U+2248
≈
Almost Equal To

U+2249
≉
Not Almost Equal To

U+224A
≊
Almost Equal or Equal To

U+224B
≋
Triple Tilde

U+224C
≌
All Equal To

U+224D
≍
Equivalent To

U+224E
≎
Geometrically Equivalent To

U+224F
≏
Difference Between

U+2250
≐
Approaches the Limit

U+2251
≑
Geometrically Equal To

U+2252
≒
Approximately Equal to or the Image Of

U+2253
≓
Image of or Approximately Equal To

U+2254
≔
Colon Equals

U+2255
≕
Equals Colon

U+2256
≖
Ring In Equal To

U+2257
≗
Ring Equal To

U+2258
≘
Corresponds To

U+2259
≙
Estimates

U+225A
≚
Equiangular To

U+225B
≛
Star Equals

U+225C
≜
Delta Equal To

U+225D
≝
Equal to By Definition

U+225E
≞
Measured By

U+225F
≟
Questioned Equal To

U+2260
≠
Not Equal To

U+2261
≡
Identical To

U+2262
≢
Not Identical To

U+2263
≣
Strictly Equivalent To

U+2264
≤
Less-Than or Equal To

U+2265
≥
Greater-Than or Equal To

U+2266
≦
Less-Than Over Equal To

U+2267
≧
Greater-Than Over Equal To

U+2268
≨
Less-Than But Not Equal To

U+2269
≩
Greater-Than But Not Equal To

U+226A
≪
Much Less-Than

U+226B
≫
Much Greater-Than

U+226C
≬
Between

U+226D
≭
Not Equivalent To

U+226E
≮
Not Less-Than

U+226F
≯
Not Greater-Than

U+2270
≰
Neither Less-Than Nor Equal To

U+2271
≱
Neither Greater-Than Nor Equal To

U+2272
≲
Less-Than or Equivalent To

U+2273
≳
Greater-Than or Equivalent To

U+2274
≴
Neither Less-Than Nor Equivalent To

U+2275
≵
Neither Greater-Than Nor Equivalent To

U+2276
≶
Less-Than or Greater-Than

U+2277
≷
Greater-Than or Less-Than

U+2278
≸
Neither Less-Than Nor Greater-Than

U+2279
≹
Neither Greater-Than Nor Less-Than

U+227A
≺
Precedes

U+227B
≻
Succeeds

U+227C
≼
Precedes or Equal To

U+227D
≽
Succeeds or Equal To

U+227E
≾
Precedes or Equivalent To

U+227F
≿
Succeeds or Equivalent To

U+2280
⊀
Does Not Precede

U+2281
⊁
Does Not Succeed

U+2282
⊂
Subset Of

U+2283
⊃
Superset Of

U+2284
⊄
Not A Subset Of

U+2285
⊅
Not A Superset Of

U+2286
⊆
Subset of or Equal To

U+2287
⊇
Superset of or Equal To

U+2288
⊈
Neither A Subset of Nor Equal To

U+2289
⊉
Neither A Superset of Nor Equal To

U+228A
⊊
Subset of with Not Equal To

U+228B
⊋
Superset of with Not Equal To

U+228C
⊌
Multiset

U+228D
⊍
Multiset Multiplication

U+228E
⊎
Multiset Union

U+228F
⊏
Square Image Of

U+2290
⊐
Square Original Of

U+2291
⊑
Square Image of or Equal To

U+2292
⊒
Square Original of or Equal To

U+2293
⊓
Square Cap

U+2294
⊔
Square Cup

U+2295
⊕
Circled Plus

U+2296
⊖
Circled Minus

U+2297
⊗
Circled Times

U+2298
⊘
Circled Division Slash

U+2299
⊙
Circled Dot Operator

U+229A
⊚
Circled Ring Operator

U+229B
⊛
Circled Asterisk Operator

U+229C
⊜
Circled Equals

U+229D
⊝
Circled Dash

U+229E
⊞
Squared Plus

U+229F
⊟
Squared Minus

U+22A0
⊠
Squared Times

U+22A1
⊡
Squared Dot Operator

U+22A2
⊢
Right Tack

U+22A3
⊣
Left Tack

U+22A4
⊤
Down Tack

U+22A5
⊥
Up Tack

U+22A6
⊦
Assertion

U+22A7
⊧
Models

U+22A8
⊨
True

U+22A9
⊩
Forces

U+22AA
⊪
Triple Vertical Bar Right Turnstile

U+22AB
⊫
Double Vertical Bar Double Right Turnstile

U+22AC
⊬
Does Not Prove

U+22AD
⊭
Not True

U+22AE
⊮
Does Not Force

U+22AF
⊯
Negated Double Vertical Bar Double Right Turnstile

U+22B0
⊰
Precedes Under Relation

U+22B1
⊱
Succeeds Under Relation

U+22B2
⊲
Normal Subgroup Of

U+22B3
⊳
Contains as Normal Subgroup

U+22B4
⊴
Normal Subgroup of or Equal To

U+22B5
⊵
Contains as Normal Subgroup or Equal To

U+22B6
⊶
Original Of

U+22B7
⊷
Image Of

U+22B8
⊸
Multimap

U+22B9
⊹
Hermitian Conjugate Matrix

U+22BA
⊺
Intercalate

U+22BB
⊻
Xor

U+22BC
⊼
Nand

U+22BD
⊽
Nor

U+22BE
⊾
Right Angle with Arc

U+22BF
⊿
Right Triangle

U+22C0
⋀
N-Ary Logical And

U+22C1
⋁
N-Ary Logical Or

U+22C2
⋂
N-Ary Intersection

U+22C3
⋃
N-Ary Union

U+22C4
⋄
Diamond Operator

U+22C5
⋅
Dot Operator

U+22C6
⋆
Star Operator

U+22C7
⋇
Division Times

U+22C8
⋈
Bowtie

U+22C9
⋉
Left Normal Factor Semidirect Product

U+22CA
⋊
Right Normal Factor Semidirect Product

U+22CB
⋋
Left Semidirect Product

U+22CC
⋌
Right Semidirect Product

U+22CD
⋍
Reversed Tilde Equals

U+22CE
⋎
Curly Logical Or

U+22CF
⋏
Curly Logical And

U+22D0
⋐
Double Subset

U+22D1
⋑
Double Superset

U+22D2
⋒
Double Intersection

U+22D3
⋓
Double Union

U+22D4
⋔
Pitchfork

U+22D5
⋕
Equal and Parallel To

U+22D6
⋖
Less-Than with Dot

U+22D7
⋗
Greater-Than with Dot

U+22D8
⋘
Very Much Less-Than

U+22D9
⋙
Very Much Greater-Than

U+22DA
⋚
Less-Than Equal to or Greater-Than

U+22DB
⋛
Greater-Than Equal to or Less-Than

U+22DC
⋜
Equal to or Less-Than

U+22DD
⋝
Equal to or Greater-Than

U+22DE
⋞
Equal to or Precedes

U+22DF
⋟
Equal to or Succeeds

U+22E0
⋠
Does Not Precede or Equal

U+22E1
⋡
Does Not Succeed or Equal

U+22E2
⋢
Not Square Image of or Equal To

U+22E3
⋣
Not Square Original of or Equal To

U+22E4
⋤
Square Image of or Not Equal To

U+22E5
⋥
Square Original of or Not Equal To

U+22E6
⋦
Less-Than But Not Equivalent To

U+22E7
⋧
Greater-Than But Not Equivalent To

U+22E8
⋨
Precedes But Not Equivalent To

U+22E9
⋩
Succeeds But Not Equivalent To

U+22EA
⋪
Not Normal Subgroup Of

U+22EB
⋫
Does Not Contain as Normal Subgroup

U+22EC
⋬
Not Normal Subgroup of or Equal To

U+22ED
⋭
Does Not Contain as Normal Subgroup or Equal

U+22EE
⋮
Vertical Ellipsis

U+22EF
⋯
Midline Horizontal Ellipsis

U+22F0
⋰
Up Right Diagonal Ellipsis

U+22F1
⋱
Down Right Diagonal Ellipsis

U+22F2
⋲
Element of with Long Horizontal Stroke

U+22F3
⋳
Element of with Vertical Bar at End of Horizontal Stroke

U+22F4
⋴
Small Element of with Vertical Bar at End of Horizontal Stroke

U+22F5
⋵
Element of with Dot Above

U+22F6
⋶
Element of with Overbar

U+22F7
⋷
Small Element of with Overbar

U+22F8
⋸
Element of with Underbar

U+22F9
⋹
Element of with Two Horizontal Strokes

U+22FA
⋺
Contains with Long Horizontal Stroke

U+22FB
⋻
Contains with Vertical Bar at End of Horizontal Stroke

U+22FC
⋼
Small Contains with Vertical Bar at End of Horizontal Stroke

U+22FD
⋽
Contains with Overbar

U+22FE
⋾
Small Contains with Overbar

U+22FF
⋿
Z Notation Bag Membership
"""


# For AST to src tracking
# start and stop indicate what tokens from the list[Token] the AST is made of
ast_src_map:dict[AST, Span] = {}




# Chain:TypeAlias = AST[Chained]
# def chain(tokens: list[Token]) -> list[Chain]: ...




# def tokenize(source: str) -> list[AST[Tokenized]]: ...
src = path.read_text()
ast = tokenize(src)
ast = post_process(ast)
ast = top_level_parse(ast)
ast = post_parse(ast)
ast = resolve(ast)
ast = typecheck(ast)


f"""
Tracking locations for debugging

token:
    src:str
    loc:Location
Chain:
    parent_tokens:list[token]
    ...
AST:
    parent_chains:list[chain]
    ...




When doing typecheck_and_resolve, I feel like we need a structure for tracking declarations present for each line of code


```
                        % () 
loop b in 1..10 (       % (b:int)             | (b:int a:int c:int) => (b:int a:int|void c:int|void)
    a = 1               % (b:int a:int)       | (b:int a:int c:int) => (b:int a:int c:int|void)
    c = 2               % (b:int a:int c:int)
)

```


perhaps it's a map for each AST in the tree
type_state: dict[AST, TypeStateLink/Node]
iteration order over an AST should maybe be the order that ASTs are executed?
then we could just iterate over the AST and for each node, make a new TypeState node linked to the previous 
(if there were any new entries), and we insert into the map with the current id(node) as key




final ASTs that make codegen easier
- no bare identifiers/typed identifiers. only express(name:str) or signature(name:str) or other specialized identifiers based on their context
---> no context should be necessary. All ASTs should be fully contextualized



FunctionLiteral:
    signature: FunctionSignature
    body: Body
    scope: Scope|None



TODO: some research around typechecking/maintaining scope for each AST in the sequence of the program
---> e.g. draw out some example programs, and trace what happens to the scope at each AST
---> especially of interest is cases that are non-linear, e.g. a variable doesn't exist on one iteration of a loop, but is present at the next, and so forth
"""



"""
Parsing algorithm:
do the simplest thing, basically what I was doing in the np prat example, but just do it with loops rather than parallelized!
while any shifts happened last time
    for non operator tokens
        determine if shifts left or right based on binding energy
        (TBD handling if Quantum. perhaps some sort of local bifurcation/copy once for both cases)

"""

