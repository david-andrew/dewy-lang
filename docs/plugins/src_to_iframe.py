import sys
import re
from urllib.parse import quote
import json

from itertools import count
counter = count(0)


def process_markdown(input_markdown):

    pattern = re.compile(r"```dewy(, *editable)?\n((.*\n)*?)```$", re.MULTILINE)

    def replacement(match):
        i = next(counter)  # give each iframe a unique id
        editable = match.group(1) is not None
        page = 'demo_only' if editable else 'src_only'
        code_block = match.group(2)[:-1]  # remove the trailing newline
        encoded_code = quote(code_block)
        iframe = f'''\
<iframe
    src="https://david-andrew.github.io/iframes/dewy/{page}?src={encoded_code}&id=DewyIframe{i}"
    style="width: 100%;"
    id="DewyIframe{i}"
    frameBorder="0"
></iframe>'''
        return iframe

    return pattern.sub(replacement, input_markdown)


if __name__ == '__main__':
    if len(sys.argv) > 1:  # we check if we received any argument
        if sys.argv[1] == "supports":
            # then we are good to return an exit status code of 0, since the other argument will just be the renderer's name
            sys.exit(0)

    # load both the context and the book representations from stdin
    context, book = json.load(sys.stdin)
    for section in book['sections']:
        section['Chapter']['content'] = process_markdown(section['Chapter']['content'])
        for subitem in section['Chapter']['sub_items']:
            subitem['Chapter']['content'] = process_markdown(subitem['Chapter']['content'])
    print(json.dumps(book))
