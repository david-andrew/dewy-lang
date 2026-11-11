"""Where a moved Dewy reader leaf's functions live in an isolated build that lacks the leaf."""

# (a leaf moved out of a Jo module without state of its own: an isolated build that has that module but
# not the leaf reads the leaf's functions from the module, a double or the real one)
LEAF_HOMES = {
    'lexer_units': 'lex.jo',
    'lexer_errors': 'lex.jo',
    'reader_service_ops': 'dewy_reader_services.jo',
    'dewy_node_ops': 'dewy_nodes.jo',
    'dewy_node_builds': 'dewy_nodes.jo',
    'dewy_node_rare': 'dewy_nodes.jo',
}
