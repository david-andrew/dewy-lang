import os
import sys


def collect(root):
    pages = []
    for name in sorted(os.listdir(root)):
        if name.endswith(".md") and not name.startswith("_"):
            pages.append(os.path.join(root, name))
    return pages


def render(path, title):
    with open(path) as f:
        text = f.read()
    return "<html><head><title>" + title + "</title></head><body>" + text + "</body></html>"


def main():
    root = sys.argv[1]
    for page in collect(root):
        html = render(page, "My Site")
        print(page, len(html))


if __name__ == "__main__":
    main()
