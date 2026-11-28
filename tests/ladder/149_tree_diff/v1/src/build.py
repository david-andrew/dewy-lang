import os
import sys


def collect(root):
    pages = []
    for name in sorted(os.listdir(root)):
        if name.endswith(".md"):
            pages.append(os.path.join(root, name))
    return pages


def render(path):
    with open(path) as f:
        text = f.read()
    return "<html><body>" + text + "</body></html>"


def main():
    root = sys.argv[1]
    for page in collect(root):
        html = render(page)
        print(page, len(html))


main()
