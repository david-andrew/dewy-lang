"""
MIR. basically taking the rich representation from AST0, and converting it to more direct flow constructs

- labels + goto
- functions
- 


C-MIR shape (small, practical)
- Program: globals + functions
- Function:
  - list of locals (with C types)
  - list of basic blocks
- BasicBlock:
  - label
  - statements
  - terminator
Statements (keep it tiny):
- tmp = CONST
- tmp = UNOP op a
- tmp = BINOP op a b
- tmp = CALL f(args...)
- tmp = LOAD addr
- STORE addr value
- tmp = ADDR_OF local/global
- tmp = GEP base offset (field/element address)
- tmp = CAST kind a
- DROP a (optional; for “evaluate for effects”)
Terminators:
- GOTO label
- IF cond THEN l1 ELSE l2
- RETURN value?


example of a basic combined loop:
```dewy
loop i in iter1 or j in iter2 ...
```

```C
L_header:
    ok1 = next1(...);
    ok2 = next2(...);
    if (!(ok1 || ok2)) goto L_exit;

    if (ok1) v1 = ...; else v1 = undefined;
    if (ok2) v2 = ...; else v2 = undefined;

    ...
    goto L_header;

L_exit:
```

"""