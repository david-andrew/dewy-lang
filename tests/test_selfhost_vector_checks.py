"""Vector constructors and binary operators produce the same code and diagnostics as their Jo twin."""

from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


def test_vector_checks_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    programs = [
        'tests/cases/optimizer/vector_operand_values.dewy',
        'tests/cases/optimizer/matrix_operand_values.dewy',
    ]
    for name, expression in [('lanes', 'vec3(1 2)'), ('mixed', 'vec2(1) + vec3(2)'),
                             ('mat_add', 'mat4() + mat4()')]:
        source = tmp_path / f'{name}.dewy'
        source.write_text(f'main=()=>printl({expression})\n')
        programs.append(source)

    results = compare_builds(compiler, tmp_path, monkeypatch, ('vector_checks',), programs)
    assert [r[2] == 0 for r in results] == [True, True, False, False, False]
    for result, diagnostic in zip(results[2:], ('needs 3 components', 'cannot apply +', 'matrices only support *')):
        assert diagnostic in result[4]
