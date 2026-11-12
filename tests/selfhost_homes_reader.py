"""Where a moved Dewy reader leaf's functions live in an isolated build that lacks the leaf."""

# (a leaf moved out of a Jo module without state of its own: an isolated build that has that module but
# not the leaf reads the leaf's functions from the module, a double or the real one)
LEAF_HOMES = {
    'parser_expr': 'parse.jo',
    'parser_forms': 'parse.jo',
    'parser_decls': 'parse.jo',
    'parser_stmts': 'parse.jo',
    'parser_loops': 'parse.jo',
    'parser_text': 'parse.jo',
    'parser_shared': 'parse.jo',
    'parser_ops': 'parse.jo',
    'lexer_line_context': 'lex.jo',
    'parser_cursor': 'parse.jo',
    'lexer_line_closes': 'lex.jo',
    'parser_positions': 'parse.jo',
    'parser_flow_nodes': 'parse.jo',
    'parser_errors': 'parse.jo',
    'parser_units': 'parse.jo',
    'lexer_units': 'lex.jo',
    'lexer_errors': 'lex.jo',
    'reader_service_ops': 'dewy_reader_services.jo',
    'dewy_node_ops': 'dewy_nodes.jo',
    'dewy_node_builds': 'dewy_nodes.jo',
    'dewy_node_rare': 'dewy_nodes.jo',
}
