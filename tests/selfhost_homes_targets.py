"""Where a moved GPU and native backend leaf's functions live in an isolated build that lacks the leaf."""

# (a leaf moved out of a Jo module without state of its own: an isolated build that has that module but
# not the leaf reads the leaf's functions from the module, a double or the real one)
LEAF_HOMES = {
    'loops_emit': 'loops.jo',
    'loops_vector_emit': 'loops.jo',
    'opt_copy_forward': 'opt.jo',
    'opt_licm': 'opt.jo',
    'optimizer_queries': 'opt.jo',
    'spirv_ops': 'spirv.jo',
    'glsl_ops': 'glsl.jo',
    'msl_ops': 'msl.jo',
    'spirv_emit': 'spirv.jo',
    'glsl_emit': 'glsl.jo',
    'msl_emit': 'msl.jo',
    'arm64_ops': 'arm64.jo',
    'x64_ops': 'x64.jo',
    'glsl_stmts': 'glsl.jo',
    'msl_stmts': 'msl.jo',
    'spirv_stmts': 'spirv.jo',
}
