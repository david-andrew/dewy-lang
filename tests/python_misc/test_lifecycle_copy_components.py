"""Move-only capability propagates through synthesized aggregate copies."""
import pytest

from dewy.reporting import ReportException, SrcFile
from dewy.semantic import check, lifecycle, ty


RESOURCE = '''OwnedToken=type of [token:int64
$__drop__
release=():>void=>{}
]
'''


@pytest.mark.parametrize('annotation,path', [
    ('array<OwnedToken>', '[]'),
    ('[resource:OwnedToken]', 'resource'),
    ('array<[resource:OwnedToken]>', '[].resource'),
    ('OwnedToken?', 'this type'),
    ('[resources:array<OwnedToken>]', 'resources[]'),
    ('dict<int64 OwnedToken>', 'values[]'),
])
def test_synthesized_copy_cannot_duplicate_a_nested_move_only_resource(annotation, path):
    source = RESOURCE + f'f=(value:{annotation}):>{annotation}=>value.copy()'
    with pytest.raises(ReportException, match='cannot copy a move-only value') as error:
        check.typecheck_and_resolve(SrcFile(None, '$no_prelude=true\n' + source))
    assert path in str(error.value)


def test_custom_copy_hook_controls_its_own_components():
    source = RESOURCE + '''Wrapper=type of [resource:OwnedToken
$__copy__
duplicate=():>Wrapper=>Wrapper[OwnedToken[42]]
]
f=(value:Wrapper):>Wrapper=>value.copy()
'''
    check.typecheck_and_resolve(SrcFile(None, '$no_prelude=true\n' + source))


def test_recursive_capability_query_terminates_and_finds_other_fields():
    # Recursive storage may revisit a node before encountering its resource
    # field. The cycle neither makes an ordinary tree move-only nor hides a
    # drop-only component reachable after that edge.
    recursive = ty.NamedType('Tree', -1)
    tree = ty.ObjectType((ty.ObjectField('children', ty.ArrayType(recursive, None)),))
    recursive.resolve(tree)
    assert lifecycle.copy_blocker(tree) is None
    resource = ty.ObjectType((), methods=(ty.MethodSpec('release', None, lifecycle='drop'),))
    with_resource = ty.ObjectType((*tree.fields, ty.ObjectField('resource', resource)))
    recursive.resolve(with_resource)
    blocker = lifecycle.copy_blocker(with_resource)
    assert blocker is not None and blocker.owner is resource
