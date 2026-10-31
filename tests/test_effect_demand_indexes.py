"""Effect site queries survive lazy kind selection, growth and invalidation."""
import subprocess

from tests.support import ROOT, compiler  # noqa: F401


def test_effect_site_index_lifecycle(compiler, tmp_path):
    source = tmp_path / 'effect_indexes.jo'
    source.write_text("".join(f"use '{ROOT / 'compiler' / name}'\n" for name in
                              ('effects.jo', 'types.jo', 'ast.jo', 'check.jo',
                               'checker_types.dewy', 'checker_tokens.dewy', 'checker_state.dewy',
                               'node_store.dewy')) + '''
init_types()
locals.resize(4)
fns.resize(4)
effect_final = true
read = mk(.ident, 0)
nodes[read].aux = i32(int(SK.local))
nodes[read].sym = 1
nodes[read].type = i32(T_INT)
decl = mk(.vardecl, 0)
nodes[decl].sym = 1
call = mk(.call, 0)
nodes[call].sym = 2
write = mk(.assign, 0)
nodes[write].a = i32(read)
# Ask uses first, then a previously undemanded write kind.
assert(effect_use_sites(2) == [call])
assert(effect_write_sites(1) == [decl, write])
assert(effect_scalar_sites(1) == [decl, write])
assert(effect_use_sites(3).len() == 0)
# Grow after all three indexes exist; query in a different order.
ref = mk(.fnref, 0)
nodes[ref].sym = 2
later = mk(.vardecl, 0)
nodes[later].sym = 1
assert(effect_scalar_sites(1) == [decl, write, later])
assert(effect_use_sites(2) == [call, ref])
assert(effect_write_sites(1) == [decl, write, later])
assert(effect_use_sites(2) == [call, ref])
# Preparation can rewrite a node without changing the arena length.
nodes[call].sym = 3
nodes[later].sym = 2
effect_ix_nodes = 0
effect_ix_locals = 0
assert(effect_write_sites(2) == [later])
assert(effect_use_sites(2) == [ref])
assert(effect_use_sites(3) == [call])
assert(effect_scalar_sites(1) == [decl, write])
# A graph reset must not retain a chain from the preceding graph.
effects_reset()
effect_final = true
assert(effect_use_sites(2) == [ref])
assert(effect_write_sites(1) == [decl, write])
print("ok")
''')
    binary = tmp_path / 'effect_indexes'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0 and ran.stdout == 'ok\n', ran.stdout + ran.stderr
