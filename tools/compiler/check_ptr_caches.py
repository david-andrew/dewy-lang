"""Check compiler table views across calls that may reallocate their storage.

Collect growth effects transitively across Jo and Dewy definitions. Only functions
that bind a view need local data flow. Branches join by union and a loop's back
edge includes each continue. Diagnostics refer to the use, not its declaration.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

COMPILER = Path(__file__).resolve().parents[2] / 'compiler'
FUNCTION = re.compile(r'^(\w+)(?:\[[^\]\n]*\])?[ \t]*=[ \t]*(?:<[^>\n]*>[ \t]*)?\(', re.M)
LITERAL = re.compile(r'''"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'|\#[^\n]*''')
CALL = re.compile(r'\b(\w+)(?:<[^<>\s()]+>)?[ \t]*\(', re.ASCII)
HOST = re.compile(r'\b\w*host(?:\[0\])?\.\w+\s*\(')
GROWERS = frozenset(('push', 'extend', 'insert', 'resize', 'reserve'))
TOP = re.compile(r'^\w+[^\n]*', re.M)
CALLBACK = re.compile(r'\blet[ \t]+(\w+)\s*:\s*<\(')
TYPE = re.compile(r'^(\w+):type\s*=', re.M)
# These operations cannot call compiler code. Receiver growth is handled separately.
BUILTINS = set('''if when loop match and or not return else in as int uint float bool str
    int8 int16 int32 int64 uint8 uint16 uint32 uint64 i8 i16 i32 i64 u8 u16 u32 u64
    f32 f64 float32 float64 len cap data min max abs mem_copy mem_set __set_len
    push extend insert resize reserve pop clear remove truncate get has fill size_of'''.split())
MUTABLE = re.compile(r'@(\w+)\s*:\s*array<(\w+)>|(\w+)\s*:\s*mut\s+(\w+)\[\]')
FREE_RECEIVER = re.compile(r'(?<![.\w])(?:push|extend|insert|resize|reserve)\s*\(\s*@?(\w+)')
METHOD = re.compile(r'\b(\w+)\.(?:push|extend|insert|resize|reserve)\s*\(')
ELEMENT = {'Node': {'nodes'}, 'TypeInfo': {'types'}, 'int32': {'lists'}, 'i32': {'lists'}}
# A compiler view is either the global/parameter itself, a bound slot such as
# xe_nodes[0], or a field reached through a host input. Plain arrays like
# exact_nodes contain IDs and have independent lifetimes.
TABLE = (r'\b(?<!\.)(?:\w+\[0\]\.)*'
         r'((?:nodes|lists|types|store)\b|\w+_(?:nodes|lists|types)(?=\[0\]))(?:\[0\])?')
ADDRESS = re.compile(TABLE + r'\.ptr\b(?!\s*\[)')
GROW = re.compile(TABLE + r'\.(?:push|extend|insert|resize|reserve)\s*\(')
FREE_GROW = re.compile(r'(?<![.\w])(?:push|extend|insert|resize|reserve)\s*\(\s*@?' + TABLE)
ASSIGN = re.compile(r'^\s*(let\s+)?(\w+)(?:\s*:\s*[^=]+)?\s*=(?![?>])\s*(.*)$')
TOKEN = re.compile(r'\b(\w+)(?:<[^<>\s()]+>)?[ \t]*\(|\b\w+\b|[()]')
UNINDEXED = re.compile(r'\.ptr\b(?!\s*\[)')
MAY_BIND = re.compile(r'(?<![=!<>?])=\s*(?:\$unsafe\s*)?[(\s]*' + ADDRESS.pattern)
GLOBAL_BIND = re.compile(r'^(?:let[ \t]+)?\w+(?::[^=\n]+)?[ \t]*=[ \t]*(?:\$unsafe\s*)?[( \t]*' + ADDRESS.pattern, re.M)
PART = re.compile(r'([^{};\n]*)([{};\n]|$)')
ALL = frozenset(('nodes', 'lists', 'types'))


def table_name(name):
    return 'nodes' if name == 'store' else name.rsplit('_', 1)[-1]


def definitions(directory, callbacks, types, diagnostics):
    for path in sorted(directory.iterdir()):
        if path.suffix not in ('.jo', '.dewy'):
            continue
        source = LITERAL.sub(' ', path.read_text())
        callbacks.update(CALLBACK.findall(source))
        # One pass over declarations gives each function its extent. Bodies
        # and continuations are indented in both compiler source languages.
        top = list(TOP.finditer(source))
        line, pos = 1, 0
        for i, declaration in enumerate(top):
            line += source.count('\n', pos, declaration.start())
            pos = declaration.start()
            header = declaration[0]
            if constructor := TYPE.match(header):
                types.add(constructor[1])
            if path.suffix == '.dewy' and '.ptr' in header and GLOBAL_BIND.match(header):
                diagnostics.append(f'{path}:{line}: store table addresses only in local variables')
            if match := FUNCTION.match(header):
                end = top[i + 1].start() if i + 1 < len(top) else len(source)
                yield path, match[1], line, source[pos:end]


def growth_effects(defs, roots, callbacks, types):
    # Visit only functions reachable from view holders. A conservative summary
    # for a host/callback ends that search. Each edge transmits at most 3 bits.
    bodies = defaultdict(list)
    for _, name, _, body in defs:
        bodies[name].append(body)
    callers, effects = defaultdict(set), defaultdict(set)
    roots = set(roots)
    known = bodies.keys() | BUILTINS | types
    pending = list(roots)
    visited = set()
    for callback in callbacks:
        effects[callback].update(ALL)
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        for body in bodies[name]:
            if ('host' in body and HOST.search(body)) or name in callbacks:
                effects[name].update(ALL)
                if name not in roots:
                    continue
            callees = set(CALL.findall(body))
            if GROWERS & callees:
                effects[name].update(table_name(t) for t in FREE_GROW.findall(body))
                effects[name].update(table_name(t) for t in GROW.findall(body))
                # A mutating helper can receive a table under a different
                # parameter name. Jo and Dewy spell mutable parameters differently.
                if params := MUTABLE.findall(body.partition(')')[0]):
                    receivers = set(METHOD.findall(body)) | set(FREE_RECEIVER.findall(body))
                    for dewy, element, jo, jo_element in params:
                        if (dewy or jo) in receivers:
                            item = element or jo_element
                            effects[name].update(ELEMENT.get(item, ALL if len(item) == 1 else ()))
            # Foreign and indirect calls have no local body to inspect.
            for unknown in callees - known:
                effects[unknown].update(ALL)
            if callees & callbacks or not callees <= known:
                effects[name].update(ALL)
                if name not in roots:
                    continue
            for callee in callees & bodies.keys():
                callers[callee].add(name)
                if callee not in visited:
                    pending.append(callee)
    work = deque(n for n in visited if effects[n])
    while work:
        name = work.popleft()
        for caller in callers[name]:
            if not effects[name] <= effects[caller]:
                effects[caller].update(effects[name])
                work.append(caller)
    return effects


def statements(body, line):
    """Keep braced Dewy blocks, including inline branches, in source order."""
    root = []
    stack = [root]
    pending = ''
    start = line
    for m in PART.finditer(body):
        statement, end = m.groups()
        if not pending:
            start = line
        statement = (pending + statement).strip()
        # A range can open with [ and close with ). Both delimiters count.
        if end == '\n' and (statement.endswith('=') or
                            statement.count('(') + statement.count('[') > statement.count(')') + statement.count(']')):
            pending = statement + ' '
            line += 1
            continue
        pending = ''
        if end == '{':
            children = []
            stack[-1].append((start, statement, children))
            stack.append(children)
        elif statement:
            stack[-1].append((start, statement, None))
        if end == '}' and len(stack) > 1:
            stack.pop()
        line += end == '\n'
    return root


def analyze(name, body, line, effects):
    # States are sets of (local, table, invalidating call). An empty call names
    # a current view. Keep both alternatives at a join until an assignment.
    issues = set()

    def expression(code, state, at):
        # Calls take effect after their arguments, including in nested calls.
        calls = []

        def apply(call, state):
            callee, grows, arguments = call
            state = {(n, t, why or callee) if t in grows else (n, t, why) for n, t, why in state}
            for n, table, why in state:
                if n in arguments and why:
                    issues.add((at, f'{name}: {n} may use an old {table} address after {why}'))
            return state

        for token in TOKEN.finditer(code):
            word = token[1] or token[0]
            member = code[token.start()-1:token.start()] == '.'
            if not member:
                for n, table, why in state:
                    if n != word:
                        continue
                    if calls and not code[token.end():].lstrip().startswith('['):
                        # An address argument must still be current when a later
                        # argument (or the callee itself) has grown the table.
                        for callee, _, arguments in reversed(calls):
                            if callee:
                                arguments.add(n)
                                break
                    if why:
                        issues.add((at, f'{name}: {n} may use an old {table} address after {why}'))
            if token[1]:
                grows = effects.get(word, ())
                if member and re.search(r'\b\w*host(?:\[0\])?\.$', code[:token.start()]):
                    grows = ALL
                elif word in GROWERS:
                    if member:
                        receiver = re.search(TABLE + r'\.$', code[:token.start()])
                    else:
                        receiver = FREE_GROW.match(code, token.start())
                    if receiver:
                        grows = (table_name(receiver[1]),)
                calls.append((word, grows, set()))
            elif word == '(':
                calls.append(('', (), set()))
            elif word == ')' and calls:
                state = apply(calls.pop(), state)
        # A call containing a braced expression can span multiple blocks.
        for call in reversed(calls):
            state = apply(call, state)
        return state

    def statement(code, state, at):
        match = ASSIGN.match(code)
        if not match:
            after = expression(code, state, at)
            # Stores consume the destination after evaluating the value.
            if store := re.match(r'^([\w.]+\[.+?)(?<![=!?<>])=(?![=?>])', code):
                expression(store[1], after, at)
            return after
        declared, target, rhs = match.groups()
        view = ADDRESS.search(rhs)
        alias = re.match(r'^\(*\s*(\w+)\s*(?:$|[+\-]|\bas\s+ptr)', rhs)
        acquired = set()
        if view and re.fullmatch(r'(?:\$unsafe\s*)?[(\s]*', rhs[:view.start()]):
            # A call returning a value from a pointer argument doesn't bind a view.
            # Growers in the offset expression run after taking the base.
            acquired = expression(rhs[view.end():], {(target, table_name(view[1]), '')}, at)
        elif alias:
            acquired.update((target, t, why) for n, t, why in state if n == alias[1])
        state = expression(rhs, state, at)
        if acquired and not declared and not any(n == target for n, _, _ in state):
            if not re.search(r'\blet\s+' + re.escape(target) + r'\b', body):
                issues.add((at, f'{name}: {target} stores a table address outside its local scope'))
        return {(n, t, why) for n, t, why in state if n != target} | acquired

    def block(items, state, breaks, continues):
        # None means no path falls through. A break/continue transfers its state
        # to the innermost loop even when nested inside a conditional block.
        i = 0
        while i < len(items) and state is not None:
            at, code, nested = items[i]
            i += 1
            if nested is None:
                state = statement(code, state, at)
                if code == 'break':
                    breaks.update(state)
                    return None
                if code == 'continue':
                    continues.update(state)
                    return None
                if re.match(r'^return\b', code):
                    return None
                continue
            if re.match(r'^loop\b', code):
                entry = state.copy()
                exits = set()
                while True:
                    back = set()
                    cond = statement(code, entry, at)
                    body_end = block(nested, cond, exits, back)
                    next_entry = entry | back | (body_end or set())
                    if next_entry == entry:
                        break
                    entry = next_entry
                state = cond | exits
                continue
            incoming = statement(code, state, at)
            branch = block(nested, incoming, breaks, continues)
            if re.match(r'^if\b', code):
                joined = branch
                while i < len(items) and items[i][1].startswith('else') and items[i][2] is not None:
                    at, other, arm = items[i]
                    i += 1
                    incoming = statement(other, incoming, at)
                    branch = block(arm, incoming, breaks, continues)
                    if branch is not None:
                        joined = (joined or set()) | branch
                    if other == 'else':
                        incoming = None
                        break
                state = joined if incoming is None else (joined or set()) | incoming
            else:
                state = incoming | (branch or set())
        return state

    block(statements(body, line), set(), set(), set())
    return sorted(issues)


def check(directory):
    callbacks, types, diagnostics = set(), set(), []
    defs = list(definitions(directory, callbacks, types, diagnostics))
    candidates = [(path, name, line, body) for path, name, line, body in defs
                  if path.suffix == '.dewy' and UNINDEXED.search(body) and MAY_BIND.search(body)]
    effects = growth_effects(defs, (name for _, name, _, _ in candidates), callbacks, types)
    yield from diagnostics
    for path, name, line, body in candidates:
        for at, issue in analyze(name, body, line, effects):
            yield f'{path}:{at}: {issue}'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', nargs='?', type=Path, default=COMPILER)
    diagnostics = list(check(parser.parse_args().directory))
    for diagnostic in diagnostics:
        print(diagnostic, file=sys.stderr)
    sys.exit(bool(diagnostics))
