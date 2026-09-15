"""Reporting a failed check must not render the entire reachable compiler."""
from dewy.reporting import SrcFile
from dewy.semantic.check import Context


def test_context_repr_does_not_expand_shared_compiler_state():
    class UnrenderableSyntax:
        def __repr__(self):
            raise AssertionError('context diagnostics must not walk synthesized syntax')

    context = Context(SrcFile(None, ''), target='x86_64')
    context.module = context
    context.synthesized.append(UnrenderableSyntax())
    rendered = repr(context)
    assert '<input>' in rendered and 'x86_64' in rendered
    assert len(rendered) < 200
