"""Reading enumerations out of compiler sources, for the tests that number them."""
import re


def dewy_enumerations(text):
    """`Name:type = 'a' | 'b'`: each union of string literals, its members as written."""
    out = {}
    for m in re.finditer(r"^(?:let\s+)?([A-Za-z_]\w*)\s*:\s*type\s*=\s*('[^'\n]*'(?:\s*\|\s*'[^'\n]*')*)\s*$", text, re.M):
        out[m.group(1)] = re.findall(r"'([^']*)'", m.group(2))
    return out


def jo_enums(text):
    """`enum Name:` and its indented members, in order."""
    out = {}
    for m in re.finditer(r'^enum\s+([A-Za-z_]\w*)\s*:[ \t]*\n((?:[ \t]+\S.*\n?)+)', text, re.M):
        out[m.group(1)] = re.findall(r'[A-Za-z_]\w*', re.sub(r'#.*', '', m.group(2)))
    return out
