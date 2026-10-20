"""Sloppy random program generator, adapted for Dewy shared-backend validation.

Upstream 6725916fc98f650372fbdf6bd72e266a74a1fe2e tools/fuzz.py; see core/LICENSE.
The runner chooses the supported feature subset explicitly. No work at import.
"""
import random


class Gen:
    def __init__(self, rnd):
        self.r = rnd
        self.lines = []
        self.ints = []      # names of int variables in scope
        self.ro = set()     # read-only ones (parameters, loop variables)
        self.floats = []
        self.arrays = []    # [int] arrays (never empty)
        self.strs = []      # str variables
        self.structs = []   # P variables
        self.parrs = []     # [P] arrays (never empty)
        self.closures = []  # fn(int) -> int values
        self.maps = []      # {int: int} maps
        self.vecs = []      # (name, lanes) of vec2/vec3/vec4 variables
        self.varrs = []     # (name, lanes) of arrays of 3 vectors
        self.depth = 0
        self.use_vec = rnd.random() < 0.5     # half the programs stay in the bootstrap compiler's subset
        self.use_new = self.use_vec and rnd.random() < 0.8
        self.unions = []    # U variables (int | str | UA)
        self.soas = []      # (soa P[] name, P[] mirror name)
        self.mats = []      # (name, rows, cols) of f64[,] variables
        self.fvs = []       # (name, n) of f64[] variables
        self.fns = []       # (name, nparams) of helper functions: int -> int
        self.n = 0

    def fresh(self, p):
        self.n += 1
        return f"{p}{self.n}"

    def emit(self, s):
        self.lines.append("    " * self.depth + s)

    # ---------------- expressions ----------------
    def iexpr(self, d=0):
        r = self.r
        if d > 3 or r.random() < 0.25:
            c = r.random()
            if d > 7:                # (leaves that hold expressions themselves stop somewhere)
                return r.choice(self.ints) if self.ints else str(r.choice([0, 1, 7, -5]))
            if c < 0.5 and self.ints: return r.choice(self.ints)
            if c < 0.65 and self.arrays:
                a = r.choice(self.arrays)
                return f"{a}[abs({self.iexpr(d + 2)}) % {a}.len()]"
            if c < 0.75 and self.arrays: return f"{r.choice(self.arrays)}.len()"
            if c < 0.8 and self.strs: return f"len({r.choice(self.strs)})"
            if c < 0.84 and self.structs: return f"{r.choice(self.structs)}.a"
            if c < 0.87 and self.closures: return f"{r.choice(self.closures)}({self.iexpr(d + 2)})"
            if c < 0.9 and self.maps: return f"({r.choice(self.maps)}.get({self.iexpr(d + 2)}) ?? -1)"
            if c < 0.92 and self.parrs:
                a = r.choice(self.parrs)
                return f"{a}[abs({self.iexpr(d + 2)}) % {a}.len()].a"
            if c < 0.95 and self.unions: return f"ushow({r.choice(self.unions)})"
            if c < 0.97 and self.mats:
                m, rows, cols = r.choice(self.mats)
                return f"fi({m}[abs({self.iexpr(d + 2)}) % {rows}, abs({self.iexpr(d + 2)}) % {cols}])"
            return str(r.choice([0, 1, 2, 3, 7, -1, -5, 100, 255, 1000, -32768, 65537, 2147483647, -2147483648]))
        op = r.choice(["+", "-", "*", "/", "%", "&", "|", "xor", "<<", ">>", "call", "neg", "if", "min", "cmpsel", "float", "match"])
        a = self.iexpr(d + 1)
        b = self.iexpr(d + 1)
        if op in ("+", "-", "*", "&", "|", "xor"): return f"({a} {op} {b})"
        if op in ("/", "%"): return f"({a} {op} (abs({b}) % 9 + 1))"
        if op in ("<<", ">>"): return f"({a} {op} (abs({b}) % 13))"
        if op == "neg": return f"(0 - {a})"
        if op == "call" and self.fns:
            name, np_ = r.choice(self.fns)
            args = ", ".join(self.iexpr(d + 2) for _ in range(np_))
            return f"{name}({args})"
        if op == "if": return f"(if {self.cond(d + 1)}: {a} else: {b})"
        if op == "min": return f"min({a}, {b})"
        if op == "cmpsel": return f"(int({a} < {b}) + int({a} == {b}) * 2)"
        if op == "float" and self.floats: return f"(fi({r.choice(self.floats)} * 3.0) % 100000)"
        if op == "match" and d <= 1 and self.ints:
            arms = []
            vals = r.sample(range(-3, 12), r.randint(1, 5))
            for v in vals: arms.append(f"{v}: {self.iexpr(4)}")
            if r.random() < 0.5: arms.append(f"20..30: {self.iexpr(4)}")
            if r.random() < 0.3: arms.append(f"'a', 'z': {self.iexpr(4)}")
            arms.append(f"_: {self.iexpr(4)}")
            return "(match " + r.choice(self.ints) + ":\n" + "".join("    " * (self.depth + 2) + arm + "\n" for arm in arms) + "    " * (self.depth + 1) + ")"
        return a

    def fexpr(self, d=0):
        r = self.r
        if d > 3 or r.random() < 0.3:
            if self.mats and d < 6 and r.random() < 0.15:
                m, rows, cols = r.choice(self.mats)
                return f"{m}[abs({self.iexpr(3)}) % {rows}, abs({self.iexpr(3)}) % {cols}]"
            if self.fvs and d < 6 and r.random() < 0.15:
                v, n = r.choice(self.fvs)
                return r.choice([f"{v}[abs({self.iexpr(3)}) % {n}]", f"sum({v})"])
            if self.floats and r.random() < 0.6: return r.choice(self.floats)
            return r.choice(["0.5", "1.25", "-3.75", "100.0", "0.1", "2.0"])
        op = r.choice(["+", "-", "*", "/", "int", "sqrt", "abs", "floor"])
        a = self.fexpr(d + 1)
        b = self.fexpr(d + 1)
        if op in "+-*": return f"({a} {op} {b})"
        if op == "/": return f"({a} / (abs({b}) + 1.0))"
        if op == "int": return f"f64({self.iexpr(d + 2)} % 1000)"
        if op == "sqrt": return f"sqrt(abs({a}))"
        if op == "abs": return f"abs({a})"
        return f"floor({a})"

    # values that own other values: copies must stay independent
    def managed_stmt(self):
        r = self.r
        a = r.choice(self.arrays)
        c = r.randint(0, 5)
        if c == 0:
            v = self.fresh("nn")
            self.emit(f"{v} = [{a}, [{self.iexpr(2)}], {a}]")
            self.emit(f"{v}[{r.randint(0, 2)}].push({self.iexpr(2)})")
            self.emit(f"{v}[0][0] = {self.iexpr(2)}")
            self.emit(f"print({v}, {a})")
        elif c == 1:
            v = self.fresh("qq")
            self.emit(f"{v} = Q({a}, {a}.len())")
            w = self.fresh("qq")
            self.emit(f"{w} = {v}")
            self.emit(f"{w}.xs[abs({self.iexpr(2)}) % {w}.xs.len()] = {self.iexpr(2)}")
            self.emit(f"if {v}.xs.len() < 40: {v}.xs.push({self.iexpr(2)})")
            # a loop over a field array: its pointer and length are read once when nothing
            # in the loop can replace or resize it (release builds)
            k = self.fresh("fk")
            self.emit(f"loop {k} in [0..{v}.xs.len()):")
            # The body may replace this array with a shorter one. Keep the
            # generated program valid while still testing length invalidation.
            self.emit(f"    if {k} >= {v}.xs.len(): break")
            self.emit(f"    {v}.xs[{k}] = {v}.xs[{k}] * 3 + {k} + {w}.xs[{k} % {w}.xs.len()]")
            c2 = r.random()
            if c2 < 0.25: self.emit(f"    if {k} == 1 and {v}.xs.len() < 40: {v}.xs.push({k})")
            elif c2 < 0.45: self.emit(f"    if {k} == 0: {w} = {v}")
            elif c2 < 0.6: self.emit(f"    if {k} == 2: {v}.xs = [{k}, {k}]")
            self.emit(f"print({v}, {w}, {a})")
        elif c == 2 and [x for x in self.arrays if x not in self.ro]:
            b = r.choice([x for x in self.arrays if x not in self.ro])
            self.emit(f"grow({b}, {self.iexpr(2)})")
            self.emit(f"print({b})")
        elif c == 3:
            v = self.fresh("rv")
            self.emit(f"{v} = rev({a})")
            self.emit(f"{v}[0] = {self.iexpr(2)}")
            self.emit(f"print({v}, {a}, rev({v}) == {a})")
        elif c == 4:
            v = self.fresh("cap")
            self.emit(f"{v} = (i: int) -> int: {a}[abs(i) % {a}.len()] + {a}.len()")
            self.emit(f"print({v}({self.iexpr(2)}))")
            if a not in self.ro:
                self.emit(f"{a}[0] = {self.iexpr(2)}")
                self.emit(f"print({v}(0), {a}[0])")
        else:
            v = self.fresh("sw")
            self.emit(f"{v} = {a}")
            if a not in self.ro:
                self.emit(f"{a}, {v} = {v}, [{self.iexpr(2)}]")
            self.emit(f"print({a}, {v})")

    def vlit(self, n):
        r = self.r
        return f"vec{n}({', '.join(r.choice(['0.5', '1.0', '-2.0', '3.25', '0.125', '-0.75', '8.0']) for _ in range(n))})"

    def vexpr(self, n, d=0):
        r = self.r
        if d > 2 or r.random() < 0.3:
            c = r.random()
            same = [v for v, k in self.vecs if k == n]
            arrs = [v for v, k in self.varrs if k == n]
            if c < 0.5 and same: return r.choice(same)
            if c < 0.7 and arrs: return f"{r.choice(arrs)}[abs({self.iexpr(3)}) % 3]"
            return self.vlit(n)
        op = r.choice(["+", "-", "*", "s*", "*s", "/s", "s-", "/v"])
        a = self.vexpr(n, d + 1)
        sc = f"f32({self.fexpr(3)})"
        if op in "+-*": return f"({a} {op} {self.vexpr(n, d + 1)})"
        if op == "s*": return f"({sc} * {a})"
        if op == "*s": return f"({a} * {sc})"
        if op == "s-": return f"({sc} - {a})"
        if op == "/v": return f"({a} / {self.vlit(n)})"
        return f"({a} / (abs({sc}) + 1.0))"

    def vstmt(self):
        r = self.r
        n = r.randint(2, 4)
        c = r.random()
        same = [v for v, k in self.vecs if k == n]
        arrs = [v for v, k in self.varrs if k == n]
        if c < 0.3 or not same:
            v = self.fresh("v")
            self.emit(f"{v} = {self.vexpr(n)}")
            self.vecs.append((v, n))
        elif c < 0.45:
            v = self.fresh("va")
            self.emit(f"{v} = [{self.vexpr(n, 2)}, {self.vexpr(n, 2)}, {self.vexpr(n, 2)}]")
            self.varrs.append((v, n))
        elif c < 0.65:
            v = r.choice(same)
            self.emit(f"{v} {r.choice(['=', '+=', '-=', '*='])} {self.vexpr(n)}")
        elif c < 0.8 and arrs:
            a = r.choice(arrs)
            i = f"abs({self.iexpr(3)}) % 3"
            self.emit(f"{a}[{i}] = {a}[{i}] * {self.vexpr(n, 2)} + {self.vexpr(n, 2)}")
            self.emit(f"print({a})")
        else:
            self.emit(f"print({r.choice(same)})")

    def cond(self, d=0):
        r = self.r
        c = r.random()
        if c < 0.6: return f"{self.iexpr(d + 1)} {r.choice(['<', '<=', '>', '>=', '==', '!='])} {self.iexpr(d + 1)}"
        if c < 0.75 and self.floats: return f"{self.fexpr(d + 1)} < {self.fexpr(d + 1)}"
        if c < 0.8 and len(self.strs) > 1: return f"{r.choice(self.strs)} {r.choice(['==', '!=', '<'])} {r.choice(self.strs)}"
        if c < 0.9: return f"({self.cond(d + 2)}) {r.choice(['and', 'or'])} ({self.cond(d + 2)})"
        return f"not ({self.cond(d + 2)})"

    # ---------------- statements ----------------
    def block(self, n):
        saved = (list(self.ints), list(self.floats), list(self.arrays), list(self.strs), list(self.structs), list(self.parrs), list(self.closures), list(self.maps), list(self.vecs), list(self.varrs),
                 list(self.unions), list(self.soas), list(self.mats), list(self.fvs))
        self.depth += 1
        for _ in range(n): self.stmt()
        if not self.lines[-1].strip() or self.lines[-1].endswith(":"): self.emit("pass")
        self.depth -= 1
        (self.ints, self.floats, self.arrays, self.strs, self.structs, self.parrs, self.closures, self.maps, self.vecs, self.varrs,
         self.unions, self.soas, self.mats, self.fvs) = saved

    def stmt(self):
        r = self.r
        if self.use_vec and r.random() < 0.1:
            self.vstmt()
            return
        if self.use_new and r.random() < 0.18:
            r.choice([self.union_stmt, self.union_stmt, self.closure_stmt, self.soa_stmt, self.nd_stmt, self.nd_stmt])()
            return
        if r.random() < 0.06 and self.arrays:
            self.managed_stmt()
            return
        if r.random() < 0.04 and self.arrays and self.depth < 3:
            a = r.choice(self.arrays)
            v = self.fresh("b")
            op = r.choice(["or", "and"])
            self.emit(f"{v} = mh({self.iexpr(2)}, {a}, macc) {op} mh({self.iexpr(2)}, {r.choice(self.arrays)}, macc)")
            self.emit(f"print({v}, {a}, macc.len())")
            return
        if r.random() < 0.05 and self.arrays and self.depth < 3:
            # index loops over a whole array (their bounds checks may be removed)
            arr = r.choice(self.arrays)
            k = self.fresh("j")
            acc = self.fresh("sum")
            self.emit(f"{acc} = 0")
            c = r.random()
            if c < 0.35:
                self.emit(f"loop {k} in [0..{arr}.len()): {acc} += {arr}[{k}] * {r.randint(1, 5)}")
            elif c < 0.6:
                n = self.fresh("n")
                self.emit(f"{n} = {arr}.len()")
                self.emit(f"loop {k} in 0..{n} - 1: {acc} xor= {arr}[{k}]")
            else:
                # counting alongside the elements
                x = self.fresh("x")
                self.emit(f"loop {k} in 0.. and {x} in {arr}: {acc} += ({k} + 1) * {x}")
            self.emit(f"print({acc})")
            return
        c = r.random()
        if c < 0.2 or not self.ints:
            v = self.fresh("i")
            self.emit(f"{v} = {self.iexpr()}")
            self.ints.append(v)
        elif c < 0.3:
            v = self.fresh("fl")
            self.emit(f"{v} = {self.fexpr()}")
            self.floats.append(v)
        elif c < 0.38:
            v = self.fresh("a")
            n = r.randint(1, 6)
            self.emit(f"{v} = [{', '.join(self.iexpr(2) for _ in range(n))}]")
            self.arrays.append(v)
        elif c < 0.42 and r.random() < 0.5:
            self.new_value()
        elif c < 0.55 and [x for x in self.ints if x not in self.ro]:
            v = r.choice([x for x in self.ints if x not in self.ro])
            self.emit(f"{v} {r.choice(['=', '+=', '-=', 'xor='])} {self.iexpr()}")
        elif c < 0.62 and self.floats:
            v = r.choice(self.floats)
            self.emit(f"{v} = {self.fexpr()}")
        elif c < 0.7 and self.arrays:
            a = r.choice(self.arrays)
            if r.random() < 0.5: self.emit(f"{a}[abs({self.iexpr(2)}) % {a}.len()] = {self.iexpr()}")
            else: self.emit(f"if {a}.len() < 64: {a}.push({self.iexpr()})")
        elif c < 0.78 and self.depth < 4:
            self.emit(f"if {self.cond()}:")
            self.block(r.randint(1, 3))
            if r.random() < 0.5:
                self.emit("else:")
                self.block(r.randint(1, 3))
        elif c < 0.85 and self.depth < 3:
            k = self.fresh("k")
            self.emit(f"loop {k} in " + r.choice([f"[0..{r.randint(1, 12)})", f"1..{r.randint(1, 12)}", f"[2..{r.randint(1, 12)}]"]) + ":")
            self.ints.append(k)
            self.ro.add(k)
            self.block(r.randint(1, 4))
            self.ints.remove(k)
        elif c < 0.9 and self.depth < 3 and self.arrays:
            x = self.fresh("x")
            self.emit(f"loop {x} in {r.choice(self.arrays)}:")
            self.ints.append(x)
            self.ro.add(x)
            self.block(r.randint(1, 3))
            self.ints.remove(x)
        elif c < 0.94 and self.depth < 3:
            w = self.fresh("w")
            self.emit(f"{w} = 0")
            self.emit(f"loop {w} < {r.randint(1, 9)} and ({self.cond()}):")
            self.depth += 1
            self.emit(f"{w} += 1")
            self.depth -= 1
            self.block(r.randint(1, 3))
        else:
            self.emit(f"print({', '.join(r.choice(self.ints) for _ in range(r.randint(1, 3)))})")

    def new_value(self):
        r = self.r
        k = r.randint(0, 5)
        if k == 0:
            v = self.fresh("s")
            self.emit(f'{v} = "{r.choice(["ab", "", "xyz", "hello"])}" + "{{{self.iexpr(2)}}}"')
            self.strs.append(v)
        elif k == 1 and self.strs:
            v = r.choice(self.strs)
            self.emit(f'if len({v}) < 40: {v} = {v} + "{r.choice("abc")}"')
            self.emit(f"print({v}, len({v}), {v}.find(\"a\"), {v}[0..min(2, len({v}))), {v}[1..], {v}.find('b'))")
        elif k == 2:
            v = self.fresh("q")
            self.emit(f"{v} = P({self.iexpr(2)}, {self.fexpr(2)})")
            self.structs.append(v)
            if r.random() < 0.5:
                self.emit(f"{v}.a += {self.iexpr(2)}")
                self.emit(f"print({v})")
        elif k == 3:
            v = self.fresh("pa")
            self.emit(f"{v} = [P({self.iexpr(2)}, 1.5), P({self.iexpr(2)}, -2.0)]")
            self.parrs.append(v)
            if r.random() < 0.6:
                self.emit(f"loop mut it in {v}:")
                self.emit(f"    it.a = it.a * 3 + {self.iexpr(3)}")
                self.emit(f"    it.b = it.b * 0.5")
            self.emit(f"print({v})")
        elif k == 4:
            v = self.fresh("cl")
            cap = self.iexpr(2)
            self.emit(f"{v}k = {cap}")
            self.emit(f"{v} = (x: int) -> int: x * 3 + {v}k")
            self.closures.append(v)
        else:
            v = self.fresh("m")
            self.emit(f"{v}: {{int: int}} = {{}}")
            self.emit(f"loop mk in [0..{r.randint(1, 20)}): {v}[(mk * 7) % 13] = mk + {self.iexpr(3)}")
            self.emit(f"print({v}.len())")
            self.maps.append(v)

    # ---------------- newer features ----------------
    def umember(self):
        r = self.r
        c = r.random()
        if c < 0.4: return self.iexpr(2)
        if c < 0.7: return f'"t{{{self.iexpr(3)}}}"'
        return f"UA({self.iexpr(2)})"

    def union_stmt(self):
        r = self.r
        c = r.random()
        if c < 0.3 or not self.unions:
            v = self.fresh("u")
            self.emit(f"{v}: U = {self.umember()}")
            self.unions.append(v)
            return
        u = r.choice(self.unions)
        if c < 0.45:
            self.emit(f"{u} = {self.umember()}")
        elif c < 0.6:
            # narrowing in if / else if / else
            self.emit(f"if {u} is int: print({u} + {self.iexpr(2)}, {u} * 2)")
            self.emit(f"else if {u} is str: print({u}, len({u}))")
            self.emit(f"else: print({u}.v * 3)")
        elif c < 0.7:
            self.emit(f"if {u} is str and len({u}) > 2: print({u}[1..])")
            self.emit(f"if {u} is int and {u} > {self.iexpr(3)}:")
            self.depth += 1
            self.emit(f"{u} = \"over\"")        # (makes it the whole union again)
            self.emit(f"print(ushow({u}))")
            self.depth -= 1
        elif c < 0.8:
            self.emit(f"match {u}:")
            self.emit(f"    int: print(\"int\", {u} - 1)")
            self.emit(f"    str: print(\"str\", {u} + \"!\")")
            self.emit(f"    UA: print(\"ua\", {u}.v)")
        elif c < 0.9:
            us = self.fresh("us")
            acc = self.fresh("ut")
            self.emit(f"{us}: U[] = [{u}, {self.umember()}, {self.umember()}]")
            self.emit(f"{us}.push({self.umember()})")
            self.emit(f"{acc} = 0")
            self.emit(f"loop x in {us}: {acc} += ushow(x)")
            self.emit(f"print({us}, {acc}, unarrow({us}[abs({self.iexpr(3)}) % {us}.len()]))")
        else:
            o = self.fresh("o")
            self.emit(f"{o}: int? = none")
            self.emit(f"if {self.cond(2)}: {o} = {self.iexpr(2)}")
            self.emit(f"if let w = {o}: print(w + 1)")
            self.emit(f"print({o} ?? -7)")

    def closure_stmt(self):
        r = self.r
        c = r.random()
        mutable = [x for x in self.ints if x not in self.ro]
        if c < 0.3:
            v = self.fresh("cc")
            self.emit(f"{v} = mkc({self.iexpr(2)})")
            self.closures.append(v)             # (each call changes its count)
        elif c < 0.55 and mutable:
            # a closure that reads a variable changed afterwards: it sees the change
            x = r.choice(mutable)
            v = self.fresh("rd")
            self.emit(f"{v} = (q: int) -> int: q * 2 + {x}")
            self.emit(f"{x} += {self.iexpr(2)}")
            self.emit(f"print({v}(1), {x})")
            self.closures.append(v)
        elif c < 0.8 and mutable:
            # a closure that changes a captured variable
            x = r.choice(mutable)
            v = self.fresh("wr")
            self.emit(f"{v} = (q: int):")
            self.emit(f"    {x} = ({x} xor q) + 1")
            for _ in range(r.randint(1, 3)): self.emit(f"{v}({self.iexpr(2)})")
            self.emit(f"print({x})")
        else:
            # closures made in a loop each see their own iteration's variables
            fs = self.fresh("fs")
            k = self.fresh("k")
            self.emit(f"{fs}: ((int) -> int)[]")
            self.emit(f"loop {k} in [0..{r.randint(1, 4)}):")
            self.emit(f"    t{k} = {k} * {r.randint(1, 9)}")
            self.emit(f"    {fs}.push((q: int) -> int: q + t{k})")
            self.emit(f"print([loop f in {fs}: f({self.iexpr(3)})])")

    def soa_stmt(self):
        r = self.r
        c = r.random()
        if c < 0.25 or not self.soas:
            v = self.fresh("so")
            n = r.randint(1, 4)
            a, b = self.fresh("ta"), self.fresh("tb")
            self.emit(f"{v}m: P[] = []")
            for _ in range(n):
                self.emit(f"{a} = {self.iexpr(2)}")
                self.emit(f"{v}m.push(P({a}, {r.choice(['0.5', '1.25', '-2.0', '3.0'])}))")
            self.emit(f"{v}: soa P[] = {v}m")
            self.soas.append((v, v + "m"))
            return
        v, m = r.choice(self.soas)
        t = self.fresh("tv")
        if c < 0.4:
            f = self.fresh("tf")
            self.emit(f"{t} = {self.iexpr(2)}")
            self.emit(f"{f} = {self.fexpr(2)}")
            self.emit(f"if {m}.len() < 30:")
            self.emit(f"    {v}.push(P({t}, {f}))")
            self.emit(f"    {m}.push(P({t}, {f}))")
        elif c < 0.5:
            self.emit(f"if {m}.len() > 1: print({v}.pop() == {m}.pop())")
        elif c < 0.65:
            i = self.fresh("ti")
            self.emit(f"{i} = abs({self.iexpr(2)}) % {m}.len()")
            self.emit(f"{t} = {self.iexpr(2)}")
            self.emit(f"{v}[{i}].a += {t}")
            self.emit(f"{m}[{i}].a += {t}")
        elif c < 0.8:
            self.emit(f"{t} = {self.iexpr(3)}")
            for name in (v, m):
                self.emit(f"loop mut p in {name}:")
                self.emit(f"    p.a = p.a * 3 + {t}")
                self.emit(f"    p.b = p.b * 0.5")
        elif c < 0.9:
            self.emit(f"{t} = {self.fexpr(3)}")
            self.emit(f"{v}.b = {v}.b .* 2.0 .+ {t}")
            self.emit(f"loop mut p in {m}: p.b = p.b * 2.0 + {t}")
        else:
            acc = self.fresh("sa")
            self.emit(f"{acc} = 0")
            self.emit(f"loop p in {v}: {acc} += p.a")
            self.emit(f"print({v}, {acc})")
        self.emit(f"if {v}.a != [loop p in {m}: p.a] or {v}.b != [loop p in {m}: p.b]: print(\"SOA MISMATCH\", {v}, {m})")

    def flit(self):
        return self.r.choice(["0.5", "1.25", "-2.0", "3.0", "0.125", "-0.75", "4.5", "10.0"])

    def nd_stmt(self):
        r = self.r
        c = r.random()
        if c < 0.2 or not self.mats:
            v = self.fresh("mt")
            rows, cols = r.randint(1, 3), r.randint(1, 4)
            if rows > 1 and r.random() < 0.6:
                self.emit(f"{v} = [" + "; ".join(", ".join(self.flit() for _ in range(cols)) for _ in range(rows)) + "]")
                if cols == 1: self.emit(f"{v} = reshape({v}, {rows}, 1)")
            else:
                self.emit(f"{v} = reshape([{', '.join(self.flit() for _ in range(rows * cols))}], {rows}, {cols})")
            self.mats.append((v, rows, cols))
            return
        if c < 0.3:
            v = self.fresh("fv")
            n = r.randint(1, 5)
            self.emit(f"{v} = [{', '.join(self.flit() for _ in range(n))}]")
            self.fvs.append((v, n))
            return
        m, rows, cols = r.choice(self.mats)
        if c < 0.45:
            # broadcasting: a scalar, a row, a column, a 1-D row, or the same shape
            other = r.choice(["s", "row", "col", "vec", "same"])
            if other == "s": rhs = f"{self.fexpr(2)}"
            elif other == "row": rhs = f"reshape([{', '.join(self.flit() for _ in range(cols))}], 1, {cols})"
            elif other == "col": rhs = f"reshape([{', '.join(self.flit() for _ in range(rows))}], {rows}, 1)"
            elif other == "vec": rhs = f"[{', '.join(self.flit() for _ in range(cols))}]"
            else: rhs = m
            op = r.choice([".+", ".-", ".*", "./"])
            if op == "./": rhs = f"(abs.({rhs}) .+ 1.0)"
            v = self.fresh("bc")
            self.emit(f"{v} = {m} .* {self.flit()} {op} {rhs}")
            self.emit(f"print({v}, {v}.shape)")
            self.mats.append((v, rows, cols))
        elif c < 0.55:
            self.emit(f"{m}[abs({self.iexpr(2)}) % {rows}, abs({self.iexpr(2)}) % {cols}] = {self.fexpr(2)}")
        elif c < 0.62:
            v = self.fresh("cp")
            self.emit(f"{v} = {m}")
            self.emit(f"{v}[0, 0] = {self.fexpr(2)}")
            self.emit(f"print({m}, {v})")
        elif c < 0.7:
            self.emit(f"print({m} * transpose({m}), transpose({m}).shape)")
        elif c < 0.74:
            self.emit(f"print(sum({m}), fsq.({m}), sqrt.(abs.({m})) .> 1.0)")
        elif c < 0.78:
            # parts and reductions along an axis
            i = f"abs({self.iexpr(3)}) % {rows}"
            j = f"abs({self.iexpr(3)}) % {cols}"
            lo = r.randint(0, rows - 1)
            self.emit(f"print({m}[{i}, ..], {m}[.., {j}], {m}[{lo}..{r.randint(lo, rows - 1)}, {r.randint(0, cols - 1)}..], sum({m}, {r.randint(0, 1)}), max({m}, {r.randint(0, 1)}))")
            if r.random() < 0.5: self.emit(f"{m}[.., {j}] = {self.fexpr(2)}")
            else: self.emit(f"{m}[{i}, ..] = [{', '.join(self.flit() for _ in range(cols))}]")
        elif c < 0.86 and self.fvs:
            v, n = r.choice(self.fvs)
            w = [x for x, k in self.fvs if k == n]
            other = r.choice(w)
            self.emit(f"{v} = {v} .* {self.fexpr(2)} .+ fsq.({other})")
            self.emit(f"print({v}, {v} .>= {other}, min({v} .* 0.0 .+ 1.0, {other}.len()))" if False else f"print({v}, {v} .>= {other})")
        elif c < 0.93:
            v = self.fresh("cb")
            a, b, cc = r.randint(1, 3), r.randint(1, 3), r.randint(1, 3)
            self.emit(f"{v} = zeros({a}, {b}, {cc})")
            self.emit(f"{v}[abs({self.iexpr(2)}) % {a}, abs({self.iexpr(2)}) % {b}, abs({self.iexpr(2)}) % {cc}] = {self.fexpr(2)}")
            self.emit(f"print({v} .+ reshape([{', '.join(self.flit() for _ in range(a))}], {a}, 1, 1), sum({v}))")
        else:
            v = self.fresh("im")
            # (a negative number in a row goes in parentheses: [a -2] is a - 2)
            el = lambda x: f"({x})" if x < 0 else str(x)
            self.emit(f"{v} = [{self.iexpr(3)} {el(r.randint(-5, 9))}; {r.randint(0, 9)} {el(r.randint(-3, 3))}]")
            self.emit(f"print({v} .* {self.iexpr(3)} .+ {r.randint(-9, 9)}, {v} * {v})")

    def program(self):
        r = self.r
        out = ["struct P:", "    a: int", "    b: f64", "",
               "# takes an array and a mut array: used inside and/or, where temporaries are conditional",
               "mh = (n: int, xs: int[], acc: mut int[]) -> bool:",
               "    if acc.len() < 50: acc.push(n + xs.len())",
               "    n % 3 == 0", "",
               "struct Q:", "    xs: int[]", "    n: int", "",
               "grow = (xs: mut int[], k: int):",
               "    if xs.len() < 40: xs.push(k)",
               "    xs[0] += k", "",
               "rev = (xs: int[]) -> int[]:",
               "    out: int[]",
               "    i = xs.len() - 1",
               "    loop i >= 0:",
               "        out.push(xs[i])",
               "        i -= 1",
               "    out", "",
               "# float to int where every compiler agrees (the C bootstrap compiler does not saturate)",
               "fi = (x: f64) -> int:",
               "    if x == x and abs(x) < 1000000000000000.0: return int(x)",
               "    0", ""]
        if self.use_new:
            out += ["struct UA:", "    v: int", "",
                    "type U = int | str | UA", "",
                    "ushow = (u: U) -> int:",
                    "    match u:",
                    "        int: u * 2",
                    "        str: len(u)",
                    "        UA: u.v + 1", "",
                    "# narrowing after early returns",
                    "unarrow = (u: U) -> int:",
                    "    if u is str: return len(u) * 10",
                    "    if u is UA: return u.v - 1",
                    "    u + 1000", "",
                    "mkc = (start: int) -> (int) -> int:",
                    "    n = start",
                    "    (k: int) -> int:",
                    "        n += k",
                    "        n", "",
                    "fsq = (x: f64) -> f64: x * 0.5 + 1.0", ""]
        # helper functions first
        for fi in range(r.randint(1, 4)):
            name = f"h{fi}"
            np_ = r.randint(1, 3)
            params = [f"p{j}" for j in range(np_)]
            self.lines = []
            self.ints, self.floats, self.arrays = list(params), [], []
            self.strs, self.structs, self.parrs, self.closures, self.maps = [], [], [], [], []
            self.vecs, self.varrs = [], []
            self.unions, self.soas, self.mats, self.fvs = [], [], [], []
            self.ro = set(params)
            self.depth = 1
            self.emit("macc: int[]")
            for _ in range(r.randint(1, 5)): self.stmt()
            body = self.lines
            ret = self.iexpr()
            out.append(f"{name} = ({', '.join(p + ': int' for p in params)}) -> int:")
            out.extend(body)
            out.append(f"    {ret}")
            out.append("")
            self.fns.append((name, np_))
        self.lines = []
        self.ints, self.floats, self.arrays = [], [], []
        self.strs, self.structs, self.parrs, self.closures, self.maps = [], [], [], [], []
        self.vecs, self.varrs = [], []
        self.unions, self.soas, self.mats, self.fvs = [], [], [], []
        self.depth = 1
        self.emit("macc: int[]")
        for _ in range(r.randint(10, 40)): self.stmt()
        if self.vecs: self.emit(f"print({', '.join(v for v, _ in self.vecs[-4:])})")
        self.emit(f"print({', '.join(self.ints[-6:]) or '0'})")
        if self.floats: self.emit(f"print({', '.join(self.floats[-4:])})")
        if self.arrays: self.emit(f"print({self.arrays[-1]})")
        out.append("main = ():")
        out.extend(self.lines)
        return "\n".join(out) + "\n"

