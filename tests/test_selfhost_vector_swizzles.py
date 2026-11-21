"""Swizzle member types, writable runs and diagnostics agree with the frozen checker."""

from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


def test_vector_swizzles_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    expressions = (
        'let v=vec4(1 2 3 4); v.yz=vec2(5 6); printl(v.zy.x)',
        'let v=ivec3(1 2 3); printl(v.bgr.r)',
        'printl(vec2(1).z)',
        'printl(vec2(1).normalized)',
        'printl(mat4().x)',
    )
    paths = []
    for i, statement in enumerate(expressions):
        source = tmp_path / f'swizzle_{i}.dewy'
        source.write_text(f'main=()=>{{{statement}}}\n')
        paths.append(source)
    results = compare_builds(compiler, tmp_path, monkeypatch, ('vector_swizzles',), paths)
    assert [r[2] == 0 for r in results] == [True, True, False, False, False]
    for result, diagnostic in zip(results[2:], ('has no component', 'normalize(v)', 'access matrix columns')):
        assert diagnostic in result[4]
