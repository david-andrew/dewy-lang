"""Resolve a module graph's service substitutions once, then apply them to its sources."""


class Redirects:
    """Record the ordered str.replace operations used by the service-home tables."""

    def __init__(self):
        self.rules = []

    def replace(self, old, new):
        self.rules.append((old, new))
        return self

    def __call__(self, text):
        for old, new in self.rules:
            text = text.replace(old, new)
        return text


def module_rewriter(transform, modules):
    redirects = Redirects()
    result = transform(redirects, modules)
    assert result is redirects
    return redirects
