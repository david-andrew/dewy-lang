"""Scalar Linux x86-64 C emission used only to optimize the compiler host.

The native compiler remains the program backend and the compiler edit loop.
This consumes versioned --host-ir records and rejects unsupported operations.
Integer registers use unsigned arithmetic for Dewy's modulo-64-bit semantics;
memcpy loads/stores preserve unaligned access without C aliasing violations.
"""
from __future__ import annotations

import collections
import json
import re
from pathlib import Path


def translate(source: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=False)
    fs = []
    f = None
    with source.open() as stream:
        if stream.readline().strip() != 'DEWY_HOST_IR 1':
            raise ValueError('Unsupported compiler-host IR version')
        records = stream.readlines()
    for line in records:
        key, _, s = line.strip().partition(' ')
        if key == 'FN':
            idx, n, ret, ni = s.split()
            f = dict(idx=int(idx), n=int(n), ret=int(ret), noinline=ni == 'true', code=[])
            fs.append(f)
        elif key in ('VT', 'KV', 'SS', 'SA', 'ARGS'):
            f[key] = json.loads(s)
        elif key == 'NAME':
            f['name'] = s
        elif key == 'I':
            op, *fields = s.split()
            f['code'].append((op, *map(int, fields)))
        elif key == 'META':
            size, main, mc, end, mt = s.split()
            size, main, end, mt = map(int, (size, main, end, mt))
        elif key == 'ROOTS':
            roots = json.loads(s)
        elif key == 'DATA':
            data = json.loads(s)
        elif key not in ('END', ''):
            raise ValueError(line[:120])
    if mt != -1:
        raise ValueError('Compiler-host C translation does not support native threads')
    if len({f['idx'] for f in fs}) != len(fs):
        raise ValueError('Duplicate function in compiler-host IR')
    types = {-1: 'void', 0: 'U', 1: 'double', 2: 'float', 3: 'U'}

    def symbol(f):
        return 'dw_' + str(f['idx']) + '_' + re.sub('[^a-zA-Z0-9_]', '_', f['name'])

    def sig(f):
        return ('__attribute__((noinline)) ' if f['noinline'] else '') + f"{types[f['ret']]} {symbol(f)}({', '.join((types[t] + ' v' + str(i) for i, t in enumerate(f['VT'][:f['n']]))) or 'void'})"

    def u(x):
        return f'UINT64_C({x & ((1 << 64) - 1)})'
    header = Path(__file__).with_name('c_host_runtime.h').read_text()
    header += '\n'.join((sig(f) + ';' for f in fs)) + '\n'
    (out / 'host.h').write_text(header)
    byidx = {f['idx']: f for f in fs}
    ops = collections.Counter()

    def translate_function(f):
        vt = f['VT']
        kv = f['KV']
        args = f['ARGS']
        ctl = []
        lines = [f"// {f['name']}", sig(f) + '{']

        def v(i):
            assert i >= 0, (f['name'], i)
            return u(kv[i]) if vt[i] == 3 else 'v' + str(i)
        for i, t in enumerate(vt):
            if i >= f['n'] and t != 3:
                lines.append(f'{types[t]} v{i};')
        for i, (sz, al) in enumerate(zip(f['SS'], f['SA'])):
            lines.append(f'_Alignas({al}) unsigned char s{i}[{max(sz, 1)}];')
        for p, (op, ty, d, a, b, c, imm) in enumerate(f['code']):
            ops[op] += 1
            expr = None
            stmt = None

            def va():
                return v(a)

            def vb():
                return v(b)

            def dest():
                return v(d)
            if op in ('nop', 'assume'):
                continue
            elif op == 'iconst':
                expr = u(imm)
            elif op == 'fconst':
                expr = f'bf{(32 if ty == 2 else 64)}({u(imm)})'
            elif op == 'mov':
                expr = va()
            elif op in ('add', 'sub', 'mul', 'and_', 'or_', 'xor', 'eq', 'ne'):
                sym = dict(add='+', sub='-', mul='*', and_='&', or_='|', xor='^', eq='==', ne='!=')[op]
                expr = f'{va()} {sym} {vb()}'
            elif op in ('lts', 'les', 'gts', 'ges', 'ltu', 'leu', 'gtu', 'geu'):
                sym = dict(lt='<', le='<=', gt='>', ge='>=')[op[:2]]
                cast = '(S)' if op[-1] == 's' else ''
                expr = f'{cast}{va()} {sym} {cast}{vb()}'
            elif op in ('shl', 'shrs', 'shru'):
                expr = f"{('(S)' if op == 'shrs' else '')}{va()} {('<<' if op == 'shl' else '>>')} ({vb()} & 63)"
            elif op in ('divs', 'divu', 'rems', 'remu'):
                expr = f"{dict(divs='sdiv', divu='udiv', rems='srem', remu='urem')[op]}({va()},{vb()})"
            elif op in ('mulhs', 'mulhu'):
                expr = f"(({('__int128' if op == 'mulhs' else 'unsigned __int128')}){('(S)' if op == 'mulhs' else '')}{va()} * {('(S)' if op == 'mulhs' else '')}{vb()}) >> 64"
            elif op in ('neg', 'not_'):
                expr = f"{('-' if op == 'neg' else '~')}{va()}"
            elif op.startswith(('sext', 'zext')):
                expr = f"({('int' if op[0] == 's' else 'uint')}{op[4:]}_t){va()}"
            elif op in ('fadd', 'fsub', 'fmul', 'fdiv', 'feq', 'fne', 'flt', 'fle', 'fgt', 'fge'):
                sym = dict(fadd='+', fsub='-', fmul='*', fdiv='/', feq='==', fne='!=', flt='<', fle='<=', fgt='>', fge='>=')[op]
                expr = f'{va()} {sym} {vb()}'
            elif op == 'fneg':
                expr = f'-{va()}'
            elif op in ('fsqrt', 'ffloor', 'fceil', 'fabs', 'ftrunc'):
                function = 'fabs' if op == 'fabs' else op[1:]
                expr = f"{function}{('f' if ty == 2 else '')}({va()})"
            elif op in ('fmin', 'fmax'):
                expr = f"{va()} {('<' if op == 'fmin' else '>')} {vb()} ? {va()} : {vb()}"
            elif op in ('i2f', 'u2f', 'f2f'):
                expr = f"({types[ty]}){('(S)' if op == 'i2f' else '')}{va()}"
            elif op == 'f2i':
                expr = f'f2i({va()})'
            elif op == 'bits2f':
                expr = f'bf{(32 if ty == 2 else 64)}({va()})'
            elif op == 'f2bits':
                expr = f'fb{(32 if ty == 2 else 64)}({va()})'
            elif op in ('load', 'store'):
                sz = c & 15
                t = ('float' if sz == 4 else 'double') if c & 32 else ('int' if c & 16 and op == 'load' else 'uint') + str(sz * 8) + '_t'
                addr = f'{va()}+{u(imm)}'
                if c & 128:
                    addr += f"+({v(b if op == 'load' else d)}<<{c >> 8 & 3})"
                if op == 'load':
                    expr = f'ld_{t}({addr})'
                else:
                    stmt = f'st_{t}({addr},{vb()});'
            elif op == 'slot':
                expr = f'(U)s{a}'
            elif op in ('gaddr', 'daddr'):
                expr = f"(U)({('gd' if op == 'gaddr' else 'rd')}+{imm})"
            elif op == 'faddr':
                expr = f'(U){symbol(byidx[imm])}'
            elif op in ('copy', 'memcpy'):
                stmt = f"host_copy((void*){va()},(void*){vb()},{(imm if op == 'copy' else v(c))});"
            elif op in ('zero', 'memset'):
                stmt = f"host_zero((void*){va()},{(0 if op == 'zero' else vb())},{(imm if op == 'zero' else v(c))});"
            elif op == 'zeroslots':
                stmt = ' '.join((f'v{x >> 1}=0;' if x & 1 else f'memset(s{x >> 1},0,sizeof s{x >> 1});' for x in args[a:a + b]))
            elif op == 'memeq':
                expr = f'((S){v(c)}<=0 || !memcmp((void*){va()},(void*){vb()},{v(c)}))'
            elif op == 'streq':
                expr = f'streq({va()},{vb()})'
            elif op in ('call', 'calli', 'callc', 'syscall', 'intr'):
                av = args[a:a + b]
                values = [v(x) for x in av]
                vs = ','.join(values)
                if op == 'call':
                    assert c in (0, 1, 2), c
                    assert imm in byidx, (f['name'], imm)
                    expr = f'{symbol(byidx[imm])}({vs})'
                elif op in ('calli', 'callc'):
                    ts = ','.join((types[vt[x]] for x in av)) or 'void'
                    if op == 'callc' and imm > 0:
                        if imm == 1:
                            raise ValueError('Compiler-host C translation requires a named variadic parameter')
                        ts = ','.join([*(types[vt[x]] for x in av[:imm - 1]), '...'])
                    expr = f'(({types[ty]} (*)({ts})){v(c)})({vs})'
                elif op == 'syscall':
                    expr = 'sc(' + ','.join(values + ['0'] * (7 - len(values))) + ')'
                elif imm == 1:
                    expr = 'initial_stack'
                elif imm == 2:
                    expr = f'dewy_host_setjmp({vs})'
                elif imm == 3:
                    expr = f'dewy_host_longjmp({vs})'
                elif imm == 6:
                    expr = f'__atomic_fetch_add((U*){values[0]},{values[1]},__ATOMIC_SEQ_CST)'
                elif imm == 7:
                    stmt = f'{{U expected={values[1]};__atomic_compare_exchange_n((U*){values[0]},&expected,{values[2]},0,__ATOMIC_SEQ_CST,__ATOMIC_SEQ_CST);{dest()}=expected;}}'
                elif imm == 8:
                    expr = 'dewy_host_stack()'
                else:
                    raise ValueError(('intr', imm))
                if expr and (d < 0 or ty < 0):
                    stmt = expr + ';'
                    expr = None
            elif op in ('block', 'loop', 'if_'):
                ctl.append((op, p))
                if op == 'loop':
                    stmt = f'L{p}:;'
                elif op == 'if_':
                    stmt = f'if(!{va()})goto E{p};'
            elif op == 'else_':
                kind, q = ctl[-1]
                assert kind == 'if_'
                ctl[-1] = ('else_', q)
                stmt = f'goto X{q}; E{q}:;'
            elif op == 'end':
                kind, q = ctl.pop()
                stmt = (f'E{q}:;' if kind == 'if_' else '') + f'X{q}:;'
            elif op in ('br', 'brif', 'brtable'):

                def target(depth):
                    k, q = ctl[-1 - depth]
                    return ('L' if k == 'loop' else 'X') + str(q)
                if op == 'br':
                    stmt = f'goto {target(imm)};'
                elif op == 'brif':
                    stmt = f'if({va()})goto {target(imm)};'
                else:
                    stmt = 'switch(' + va() + '){' + ''.join((f'case {k}:goto {target(depth)};' for k, depth in enumerate(args[c:c + b]))) + f'default:goto {target(imm)};' + '}'
            elif op == 'ret':
                stmt = 'return' + (' ' + va() if a >= 0 and f['ret'] >= 0 else '') + ';'
            elif op == 'trap':
                stmt = '__builtin_trap();'
            elif op == 'select':
                expr = f'{va()} ? {vb()} : {v(c)}'
            else:
                raise ValueError(op)
            if expr is not None:
                if vt[d] != 3:
                    lines.append(f'{dest()}={expr};')
            elif stmt is not None:
                lines.append(stmt)
        assert not ctl
        lines += ['__builtin_unreachable();', '}']
        return '\n'.join(lines) + '\n'
    chunks = []
    body = ''
    ins = 0
    for f in fs:
        body += translate_function(f)
        ins += len(f['code'])
        if ins >= 15000:
            p = out / f'unit{len(chunks)}.c'
            p.write_text('#include "host.h"\n' + body)
            chunks.append(p.name)
            body = ''
            ins = 0
    if body:
        p = out / f'unit{len(chunks)}.c'
        p.write_text('#include "host.h"\n' + body)
        chunks.append(p.name)
    runtime = '#include "host.h"\n_Alignas(64) unsigned char gd[' + str(size + 8) + '];\n_Alignas(64) unsigned char rd[]={' + ','.join(map(str, data)) + '};\nU initial_stack;\n'
    runtime += 'void dewy_host_entry(U stack){initial_stack=stack;st_uint64_t((U)gd,stack);' + ''.join((f'{symbol(byidx[x])}();' for x in roots))
    if main >= 0:
        runtime += ('U status=' if mc == 'true' else '') + f'{symbol(byidx[main])}();'
    elif mc == 'true':
        raise ValueError('Integer entry result without a main function')
    if end >= 0:
        runtime += f'{symbol(byidx[end])}();'
    runtime += 'sc(231,' + ('status' if mc == 'true' else '0') + ',0,0,0,0,0);__builtin_unreachable();}\n'
    (out / 'runtime.c').write_text(runtime)
    chunks.append('runtime.c')
    (out / 'start.S').write_text(Path(__file__).with_name('c_host_start.S').read_text())
    (out / 'manifest.json').write_text(json.dumps({'units': chunks, 'functions': len(fs), 'ops': ops, 'source': str(source)}, indent=2) + '\n')
    return {'units': chunks, 'functions': len(fs), 'ops': dict(ops), 'source': str(source)}
