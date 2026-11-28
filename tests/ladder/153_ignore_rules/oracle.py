"""Independent ignore-rule check over the same rules and paths, by regular
expressions; run with --write to refresh expected.out."""
from pathlib import Path
import json
import re
import sys

HERE = Path(__file__).parent


class Bad(Exception):
    pass


def command_line():
    return json.loads((HERE.parent / 'ladder.json').read_text())['programs'][HERE.name]['args']


def translate(body):
    """A glob body as a regular expression over a whole path."""
    out, i = [], 0
    while i < len(body):
        ch = body[i]
        if ch == '\\':
            if i + 1 >= len(body):
                raise Bad('a pattern cannot end with `\\`')
            out.append(re.escape(body[i + 1]))
            i += 2
        elif ch == '*':
            stop = i
            while stop < len(body) and body[stop] == '*':
                stop += 1
            whole = (i == 0 or body[i - 1] == '/') and (stop == len(body) or body[stop] == '/')
            if stop - i >= 2 and whole:
                if stop < len(body):
                    out.append('(?:.*/)?')
                    stop += 1
                else:
                    out.append('.*')
            else:
                out.append('[^/]*')
            i = stop
        elif ch == '?':
            out.append('[^/]')
            i += 1
        elif ch == '[':
            j = i + 1
            if j < len(body) and body[j] == '!':
                j += 1
            if j < len(body) and body[j] == ']':
                j += 1
            close = body.find(']', j)
            if close < 0:
                raise Bad(f'`[` at {i + 1} has no closing `]`')
            inside = body[i + 1:close]
            negated = inside.startswith('!')
            members = inside[1:] if negated else inside
            parts, k = [], 0
            while k < len(members):
                if k + 2 < len(members) and members[k + 1] == '-':
                    parts.append(f'{re.escape(members[k])}-{re.escape(members[k + 2])}')
                    k += 3
                else:
                    parts.append(re.escape(members[k]))
                    k += 1
            out.append(f'(?!/)[{"^" if negated else ""}{"".join(parts)}]')
            i = close + 1
        else:
            out.append(re.escape(ch))
            i += 1
    return re.compile(''.join(out), re.DOTALL)


def read_rules(text, out):
    rules = []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        if not line or line.startswith('#'):
            continue
        negated = line.startswith('!')
        body = line[1:] if negated else line
        dir_only = body.endswith('/') and not body.endswith('\\/')
        if body.endswith('/'):
            body = body[:-1]
        anchored = '/' in body
        if body.startswith('/'):
            body = body[1:]
        if not body:
            out.append(f'rule {n}: `{line}` has no pattern')
            continue
        try:
            rules.append(dict(line=n, source=line, regex=translate(body), negated=negated, dir_only=dir_only, anchored=anchored))
        except Bad as bad:
            out.append(f'rule {n}: {bad} in `{line}`')
    return rules


def applies(rule, path, is_dir):
    if rule['dir_only'] and not is_dir:
        return False
    target = path if rule['anchored'] else path.rsplit('/', 1)[-1]
    return rule['regex'].fullmatch(target) is not None


def decide(rules, path, is_dir):
    found = None
    for rule in rules:
        if applies(rule, path, is_dir):
            found = rule
    return found


def judge(rules, path):
    parts = path.split('/')
    for k in range(1, len(parts)):
        directory = '/'.join(parts[:k])
        rule = decide(rules, directory, True)
        if rule is not None and not rule['negated']:
            return True, rule, directory
    rule = decide(rules, path, False)
    return rule is not None and not rule['negated'], rule, ''


def run(argv, paths_text):
    out = []
    rules = read_rules((HERE / Path(argv[1]).name).read_text(), out)
    used = {}
    paths = [line.strip() for line in paths_text.splitlines() if line.strip()]
    ignored = 0
    for path in paths:
        hit, rule, via = judge(rules, path)
        ignored += hit
        word = 'ignored' if hit else 'kept   '
        if rule is None:
            out.append(f'{word} {path}')
            continue
        used[rule['line']] = used.get(rule['line'], 0) + 1
        where = f' in {via}/' if via else ''
        out.append(f'{word} {path}  (rule {rule["line"]}: {rule["source"]}{where})')
    out.append(f'{ignored} of {len(paths)} paths ignored')
    for rule in rules:
        count = used.get(rule['line'], 0)
        out.append(f'rule {rule["line"]} `{rule["source"]}` ' + (f'decides {count}' if count else 'decides nothing'))
    return '\n'.join(out) + '\n'


if __name__ == '__main__':
    expected = HERE / 'expected.out'
    result = run(['ignore_rules'] + command_line(), (HERE / 'stdin.txt').read_text())
    if sys.argv[1:] == ['--write']:
        expected.write_text(result)
    elif expected.read_text() != result:
        sys.exit('expected.out differs from the ignore-rule check')
