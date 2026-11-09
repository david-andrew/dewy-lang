"""Where a moved process and driver leaf's functions live in an isolated build that lacks the leaf."""

# (a leaf moved out of a Jo module without state of its own: an isolated build that has that module but
# not the leaf reads the leaf's functions from the module, a double or the real one)
LEAF_HOMES = {
    'watch_ops': 'watch.jo',
    'watch_drive': 'watch.jo',
    'repl_ops': 'repl.jo',
    'fused_ops': 'fused.jo',
    'par_ops': 'par.jo',
    'proc_sys': 'watch.jo',
    'repl_drive': 'repl.jo',
    'fused_ir': 'fused.jo',
    'par_drive': 'par.jo',
    'driver_cli': 'main.jo',
}
