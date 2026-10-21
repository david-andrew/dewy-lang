"""Regex behavior through Dewy, with an independent oracle for shared syntax."""
import json
import re
import random

import pytest

from tests.support import compiler, run_value_batch


def quote(text):
    # Dewy interpolates braces; JSON supplies the other string escapes.
    return json.dumps(text, ensure_ascii=False).replace('{', r'\{').replace('}', r'\}')


def expected_matches(pattern, text):
    compiled = re.compile(pattern, re.MULTILINE)
    offset = 0
    result = []
    while offset <= len(text):
        match = compiled.search(text, offset)
        if match is None:
            break
        result.append(match)
        # Dewy advances one code point after an empty match.
        offset = match.end() + (match.start() == match.end())
    return result


def oracle_cases():
    # Repeated empty captures differ across regex engines; use a noncapturing
    # group for that stress case, while checking nonempty repeated captures.
    patterns = [r'(a|ab)+', r'(ab|a)+', r'a*?b|a', r'a+b', r'(?:a*)*b',
                r'(a|aa)*c', r'a{2,5}?', r'(a+?)(b*)', r'[^a]+', r'[a-z]+',
                r'(?i)[a-c]+', r'\b[a-z]+\b', r'^a.*$', r'(?:ab)?c',
                r'(a)?(b+)', r'.*?b', r'a*', r'', r'[^é]+!', r'(é|日)+']
    texts = ['ab aaab abc\naaa\nBBA! é日!',
             'x' * 300 + ' aaab abc\naaa\nBBA! é日!',
             'ab' * 150 + 'aab', 'é日' * 80 + '日本語!']
    pairs = [(p, t) for p in patterns for t in texts]
    rng = random.Random(481)
    # Cross the DFA threshold with varied ordered alternatives and quantifiers.
    for _ in range(40):
        atom = rng.choice(['a', 'b', '[ab]', '[^b]', '(?:ab|a)', '(?:a|ab)'])
        quantifier = rng.choice(['*', '+', '?', '*?', '+?', '{2,5}'])
        tail = rng.choice(['a', 'b', '|a', '|ab', '(a|b)', '$'])
        text = ''.join(rng.choice('aab ') for _ in range(rng.choice([255, 256, 257, 400])))
        pairs.append((atom + quantifier + tail, text))
    # This suffix-recognition DFA has exponentially many possible states. A
    # deterministic varied input exercises the 2,000-state fallback limit.
    wide = ''.join(rng.choice('ab') for _ in range(12000))
    pairs.append(('[ab]*a[ab]{11}', wide))
    for index, (pattern, text) in enumerate(pairs):
        matches = expected_matches(pattern, text)
        # Compare every match, including byte offsets and all capture groups.
        starts = [len(text[:m.start()].encode()) for m in matches]
        ends = [len(text[:m.end()].encode()) for m in matches]
        array = lambda values: '[' + ' '.join(map(str, values)) + ']'
        body = [f'let text={quote(text)} let r=regex({quote(pattern)})',
                'let found=text.find_all(r)',
                f'if found.length not=?{len(matches)} return 1',
                f'let starts:array<int64>={array(starts)}',
                f'let ends:array<int64>={array(ends)}',
                'loop i in [0..found.length) {',
                'if found[i].start not=?starts[i] or found[i].end not=?ends[i] return 2',
                '}',
                f'if text.contains(r) not=?{str(bool(matches)).lower()} return 3',
                f'if text.matches(r) not=?{str(re.fullmatch(pattern, text, re.MULTILINE) is not None).lower()} return 4']
        # A compact table keeps large repeated-match tests inexpensive to compile.
        expected = ['|'.join([m.group(), *(g or '' for g in m.groups())]) for m in matches]
        body += ['let contents:array<string>=[' + ' '.join(map(quote, expected)) + ']',
                 'loop i in [0..found.length) {',
                 'let actual=found[i].text',
                 'loop group in found[i].groups {actual+="|"+group}',
                 'if actual not=?contents[i] return 5', '}', 'return 42']
        yield f'regex-oracle-{index}', 'main=()=>{\n' + '\n'.join(body) + '\n}'


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_core_regex_oracle(compiler, tmp_path, target, release):
    cases = dict(oracle_cases())
    results = run_value_batch(compiler, tmp_path, cases, release, target)
    for name, (code, output) in results.items():
        assert code == '42', (name, cases[name], code, output)


@pytest.mark.core_quick
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_core_regex_operations(compiler, tmp_path, target, release):
    cases = {
        'regex-replace-split': r'''main=()=>{
let date=regex(r"(\d{4})-(\d\d)-(\d\d)")
if "due 2026-10-14!".replace(date "$3/$2/$1") not=?"due 14/10/2026!" return 1
if "a, b;c".split(regex(r"[,;]\s*")) not=?["a" "b" "c"] return 2
if "ab".split(regex("")) not=?["a" "b"] return 3
if "x".replace(regex("y*") "-") not=?"-x-" return 4
let replace_word=(m:Match)=>m.groups[0].upper()
if "ab ab ab".replace(regex("(ab) ?") @replace_word) not=?"ABABAB" return 5
return 42}''',
        'regex-offsets': r'''main=()=>{
let text="ab".repeat(200)+"aab" let r=regex("a+b")
let first=text.find(r 390)
if first is?none return 1
if first.start not=?390 return 1
let negative=text.find(r (-10))
if negative is?none return 2
if negative.start not=?0 return 2
if text.find(r 404) isnt?none return 3
let last=text.find(regex("")403)
if last is?none return 4
if last.start not=?403 return 4
if "".find(regex("")1) isnt?none return 5
return 42}''',
        'regex-malformed': r'''main=()=>{
let text="x".repeat(300)+str_from_bytes([195 65] as array<uint8>)+"B".repeat(3)
let found=text.find_all(regex("[A-Z]+"))
if found.length not=?1 or found[0].start not=?301 or found[0].text not=?"ABBB" return 1
return 42}''',
        'regex-errors': r'''main=()=>{
loop pattern in ["(" "[" "*" r"a{4,2}" "(?x)a"] {
if regex_error(pattern) is?none return 1
}
loop pattern in ["" "(?:a|b)*" r"a{2,5}?" "(?i)abc"] {
if regex_error(pattern) isnt?none return 2
}
return 42}''',
    }
    results = run_value_batch(compiler, tmp_path, cases, release, target)
    for name, (code, output) in results.items():
        assert code == '42', (name, code, output)
