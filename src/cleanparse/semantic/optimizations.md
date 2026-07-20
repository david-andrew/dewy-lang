Optimizations and semantic contracts in Dewy.
> In no specified order

## inferred integer width
unless a width is specified, all integers behave as if they have arbitrary precision
e.g.
```
x:int = 20     # x:bigint = 20
y = 10         # y:bigint = 10
Z:uint32 = 30  # z:uint32 = 30
```

There shall be an optimization pass that analyzes the possible range any given variable could take on, and when that range fits within a fixed width size, the compiler will make use of that fixed-width int instead of the more general bigint.

> note that explicitly annotated int widths will rollover and behave as that width. the semantic contract is anything else not explicitly specified will behave as if it was infinite precision, even if that precision was not needed under the hood