"""Where a moved editor (IDE, LSP, formatter) leaf's functions live in an isolated build that lacks the leaf."""

# (a leaf moved out of a Jo module without state of its own: an isolated build that has that module but
# not the leaf reads the leaf's functions from the module, a double or the real one)
LEAF_HOMES = {
    'ide_ops': 'ide.jo',
    'lsp_handlers': 'lsp.jo',
    'ide_index': 'ide.jo',
    'lsp_ops': 'lsp.jo',
    'ide_text': 'ide.jo',
    'lsp_text': 'lsp.jo',
    'lsp_requests': 'lsp.jo',
    'fmt_ops': 'fmt.jo',
    'lsp_fixes': 'lsp.jo',
    'lsp_drive': 'lsp.jo',
    'ide_decls': 'ide.jo',
}
