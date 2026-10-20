// Adapted from Sloppy's dependency-free LSP client at 235e19a.
// Copyright (c) 2026 David Samson. MIT; see THIRD_PARTY_NOTICES.md.
const cp = require('child_process');
const { compilerFor, processCommand } = require('./compiler');

// Semantic token types and modifiers, in the order of the server's legend.
const tokenTypes = ['namespace', 'type', 'struct', 'enum', 'parameter', 'variable', 'property', 'enumMember', 'function', 'method'];
const tokenModifiers = ['declaration', 'readonly', 'defaultLibrary'];

// Content-Length framed JSON-RPC over the compiler's standard input/output.
class Connection {
    constructor(command, cwd, output, notification, exited) {
        this.pending = new Map();
        this.nextId = 1;
        this.buffer = Buffer.alloc(0);
        this.closed = false;
        this.ready = false;
        this.notification = notification;
        this.exited = exited;
        this.proc = cp.spawn(...processCommand(command, ['lsp'], { cwd, stdio: ['pipe', 'pipe', 'pipe'] }));
        this.proc.stdout.on('data', (chunk) => this.receive(chunk));
        this.proc.stderr.on('data', (chunk) => output.append(chunk.toString()));
        this.proc.stdin.on('error', (error) => output.appendLine(error.message));
        this.proc.on('error', (error) => {
            output.appendLine(`Cannot start ${command} lsp: ${error.message}. Check dewy.core.path.`);
            this.close(false);
        });
        this.proc.on('exit', () => this.close(true));
    }

    close(ran) {
        if (this.closed) return;
        this.closed = true;
        for (const pending of this.pending.values()) pending.resolve(null);
        this.pending.clear();
        this.exited(ran);
    }

    receive(chunk) {
        this.buffer = Buffer.concat([this.buffer, chunk]);
        for (;;) {
            const end = this.buffer.indexOf('\r\n\r\n');
            if (end < 0) return;
            const match = /content-length:\s*(\d+)/i.exec(this.buffer.subarray(0, end).toString('ascii'));
            if (!match) { this.proc.kill(); return; }
            const size = Number(match[1]);
            if (this.buffer.length < end + 4 + size) return;
            const body = this.buffer.subarray(end + 4, end + 4 + size).toString('utf8');
            this.buffer = this.buffer.subarray(end + 4 + size);
            let message;
            try { message = JSON.parse(body); } catch { continue; }
            if (message.id !== undefined && message.method === undefined) {
                const pending = this.pending.get(message.id);
                if (!pending) continue;
                this.pending.delete(message.id);
                pending.resolve(message.error ? null : message.result, message.error);
            } else if (message.method) this.notification(message.method, message.params);
        }
    }

    send(message) {
        if (this.closed || !this.proc.stdin.writable) return;
        const body = Buffer.from(JSON.stringify(message), 'utf8');
        this.proc.stdin.write(`Content-Length: ${body.length}\r\n\r\n`);
        this.proc.stdin.write(body);
    }

    notify(method, params) { this.send({ jsonrpc: '2.0', method, params }); }

    // The result, or null (no server, cancelled, failed). With errors, a failure the server
    // explains (a rename it refuses) rejects with its message instead.
    request(method, params, token, errors = false) {
        if (this.closed || token?.isCancellationRequested) return Promise.resolve(null);
        const id = this.nextId++;
        return new Promise((resolve, reject) => {
            let cancellation;
            const done = (value, error) => {
                clearTimeout(timer);
                cancellation?.dispose();
                this.pending.delete(id);
                if (error && errors) reject(new Error(error.message));
                else resolve(value);
            };
            const timer = setTimeout(() => done(null), 10000);
            timer.unref();
            this.pending.set(id, { resolve: done });
            this.send({ jsonrpc: '2.0', id, method, params });
            if (token) cancellation = token.onCancellationRequested(() => {
                this.notify('$/cancelRequest', { id });
                done(null);
            });
        });
    }

    stop() {
        this.request('shutdown', null).then(() => this.notify('exit', null));
        const timer = setTimeout(() => this.proc.kill(), 1000);
        timer.unref();
    }
}

let active;

function activate(context, vscode) {
    const output = vscode.window.createOutputChannel('Dewy Core');
    const diagnostics = vscode.languages.createDiagnosticCollection('dewy-core');
    let client = null;
    let disposed = false;
    let restarts = 0;
    let restartTimer;
    const isDewy = (doc) => doc.languageId === 'dewy' && doc.uri.scheme === 'file';
    const document = (doc) => ({ uri: doc.uri.toString() });
    const position = (p) => new vscode.Position(p.line, p.character);
    const range = (r) => new vscode.Range(position(r.start), position(r.end));
    const location = (l) => new vscode.Location(vscode.Uri.parse(l.uri), range(l.range));
    const edit = (workspaceEdit) => {
        const out = new vscode.WorkspaceEdit();
        for (const [uri, edits] of Object.entries(workspaceEdit?.changes || {})) {
            for (const item of edits) out.replace(vscode.Uri.parse(uri), range(item.range), item.newText);
        }
        return out;
    };
    const lspRange = (r) => ({ start: { line: r.start.line, character: r.start.character },
        end: { line: r.end.line, character: r.end.character } });
    // (the server checked again: types, hints and what names are may have changed)
    const results = new vscode.EventEmitter();
    const symbol = (item) => {
        const value = new vscode.DocumentSymbol(item.name, item.detail || '', item.kind - 1,
            range(item.range), range(item.selectionRange));
        value.children = (item.children || []).map(symbol);
        return value;
    };
    const at = (doc, pos) => ({ textDocument: document(doc), position: { line: pos.line, character: pos.character } });
    const ready = () => client && client.ready ? client : null;
    const open = (doc) => {
        if (isDewy(doc)) ready()?.notify('textDocument/didOpen', {
            textDocument: { ...document(doc), languageId: 'dewy', version: doc.version, text: doc.getText() },
        });
    };
    const ask = (method, params, token) => ready()?.request(method, params, token) || Promise.resolve(null);

    function start() {
        clearTimeout(restartTimer);
        if (disposed || client || !vscode.workspace.isTrusted) return;
        const folders = (vscode.workspace.workspaceFolders || []).filter((f) => f.uri.scheme === 'file');
        const command = compilerFor(vscode, folders[0]?.uri);
        if (!command) {
            output.appendLine('No Dewy compiler: set dewy.core.path, or install a platform build of the extension.');
            return;
        }
        const conn = new Connection(command, folders[0]?.uri.fsPath, output, (method, params) => {
            if (client !== conn || method !== 'textDocument/publishDiagnostics') return;
            const doc = vscode.workspace.textDocuments.find((d) => d.uri.toString() === params.uri);
            if (doc && typeof params.version === 'number' && params.version < doc.version) return;
            diagnostics.set(vscode.Uri.parse(params.uri), params.diagnostics.map((d) => {
                const diag = new vscode.Diagnostic(range(d.range), d.message, (d.severity || 1) - 1);
                diag.source = 'dewy-core';
                return diag;
            }));
            results.fire();
        }, (ran) => {
            if (client !== conn) return;
            client = null;
            diagnostics.clear();
            if (ran && !disposed && restarts < 3) {
                restarts++;
                restartTimer = setTimeout(start, 500 * restarts);
            }
        });
        client = conn;
        conn.request('initialize', {
            processId: process.pid,
            rootUri: folders[0]?.uri.toString() || null,
            workspaceFolders: folders.map((f) => ({ uri: f.uri.toString(), name: f.name })),
            capabilities: {},
        }).then((result) => {
            if (client !== conn || !result) return;
            conn.notify('initialized', {});
            conn.ready = true;
            for (const doc of vscode.workspace.textDocuments) open(doc);
            results.fire();
        });
    }

    function restart() {
        clearTimeout(restartTimer);
        restarts = 0;
        const old = client;
        client = null;
        old?.stop();
        diagnostics.clear();
        start();
    }

    const watcher = vscode.workspace.createFileSystemWatcher('**/*.{dewy,jo}');
    const changed = (type) => (uri) => {
        if (vscode.workspace.textDocuments.some((doc) => doc.uri.toString() === uri.toString())) return;
        ready()?.notify('workspace/didChangeWatchedFiles', { changes: [{ uri: uri.toString(), type }] });
    };
    const selector = { language: 'dewy', scheme: 'file' };
    context.subscriptions.push(output, diagnostics, watcher, results,
        watcher.onDidCreate(changed(1)), watcher.onDidChange(changed(2)), watcher.onDidDelete(changed(3)),
        vscode.workspace.onDidOpenTextDocument(open),
        vscode.workspace.onDidChangeTextDocument((event) => {
            const doc = event.document;
            if (!isDewy(doc) || event.contentChanges.length === 0) return;
            ready()?.notify('textDocument/didChange', {
                textDocument: { ...document(doc), version: doc.version },
                contentChanges: [{ text: doc.getText() }],
            });
        }),
        vscode.workspace.onDidCloseTextDocument((doc) => {
            if (!isDewy(doc)) return;
            diagnostics.delete(doc.uri);
            ready()?.notify('textDocument/didClose', { textDocument: document(doc) });
        }),
        vscode.workspace.onDidSaveTextDocument((doc) => {
            if (isDewy(doc)) ready()?.notify('textDocument/didSave', { textDocument: document(doc) });
        }),
        vscode.languages.registerHoverProvider(selector, {
            async provideHover(doc, pos, token) {
                const result = await ask('textDocument/hover', at(doc, pos), token);
                return result?.contents ? new vscode.Hover(new vscode.MarkdownString(result.contents.value)) : null;
            },
        }),
        vscode.languages.registerDefinitionProvider(selector, {
            async provideDefinition(doc, pos, token) {
                const result = await ask('textDocument/definition', at(doc, pos), token);
                if (!result) return null;
                return Array.isArray(result) ? result.map(location) : location(result);
            },
        }),
        vscode.languages.registerReferenceProvider(selector, {
            async provideReferences(doc, pos, context, token) {
                const result = await ask('textDocument/references', { ...at(doc, pos), context }, token);
                return result?.map(location) ?? null;
            },
        }),
        vscode.languages.registerDocumentSymbolProvider(selector, {
            async provideDocumentSymbols(doc, token) {
                const version = doc.version;
                const result = await ask('textDocument/documentSymbol', { textDocument: document(doc) }, token);
                return result && doc.version === version ? result.map(symbol) : null;
            },
        }),
        vscode.languages.registerDocumentHighlightProvider(selector, {
            async provideDocumentHighlights(doc, pos, token) {
                const version = doc.version;
                const result = await ask('textDocument/documentHighlight', at(doc, pos), token);
                if (!result || doc.version !== version) return null;
                return result.map((item) => new vscode.DocumentHighlight(range(item.range), (item.kind || 1) - 1));
            },
        }),
        vscode.languages.registerDocumentFormattingEditProvider(selector, {
            async provideDocumentFormattingEdits(doc, options, token) {
                const version = doc.version;
                const result = await ask('textDocument/formatting', { textDocument: document(doc), options }, token);
                if (!result || doc.version !== version) return null;
                return result.map((edit) => new vscode.TextEdit(range(edit.range), edit.newText));
            },
        }),
        vscode.languages.registerCompletionItemProvider(selector, {
            async provideCompletionItems(doc, pos, token) {
                const result = await ask('textDocument/completion', at(doc, pos), token);
                if (!result) return null;
                const items = Array.isArray(result) ? result : result.items || [];
                return new vscode.CompletionList(items.map((item) => {
                    // LSP kinds are one-based; VS Code's corresponding enum is zero-based.
                    const completion = new vscode.CompletionItem(item.label, (item.kind || 1) - 1);
                    completion.detail = item.detail;
                    completion.sortText = item.sortText;
                    completion.filterText = item.filterText;
                    completion.insertText = item.insertText;
                    if (item.textEdit) {
                        completion.range = range(item.textEdit.range);
                        completion.insertText = item.textEdit.newText;
                    }
                    if (item.command) completion.command = item.command;
                    return completion;
                }), result.isIncomplete || false);
            },
        }, '.', '$', '/', '"'),
        vscode.languages.registerRenameProvider(selector, {
            async prepareRename(doc, pos, token) {
                if (!ready()) throw new Error('The Dewy language server is not running.');
                const result = await ready().request('textDocument/prepareRename', at(doc, pos), token, true);
                return result ? range(result) : null;
            },
            async provideRenameEdits(doc, pos, newName, token) {
                if (!ready()) return null;
                const result = await ready().request('textDocument/rename', { ...at(doc, pos), newName }, token, true);
                return result ? edit(result) : null;
            },
        }),
        vscode.languages.registerSignatureHelpProvider(selector, {
            async provideSignatureHelp(doc, pos, token) {
                const result = await ask('textDocument/signatureHelp', at(doc, pos), token);
                if (!result?.signatures?.length) return null;
                const help = new vscode.SignatureHelp();
                help.signatures = result.signatures.map((item) => {
                    const documentation = item.documentation?.value ?? item.documentation;
                    const signature = new vscode.SignatureInformation(item.label,
                        documentation ? new vscode.MarkdownString(documentation) : undefined);
                    signature.parameters = (item.parameters || []).map((p) => new vscode.ParameterInformation(p.label));
                    return signature;
                });
                help.activeSignature = result.activeSignature || 0;
                help.activeParameter = result.activeParameter || 0;
                return help;
            },
        }, { triggerCharacters: ['('], retriggerCharacters: [' ', ')', '='] }),
        vscode.languages.registerInlayHintsProvider(selector, {
            onDidChangeInlayHints: results.event,
            async provideInlayHints(doc, visible, token) {
                const version = doc.version;
                const result = await ask('textDocument/inlayHint', { textDocument: document(doc), range: lspRange(visible) }, token);
                if (!result || doc.version !== version) return null;
                return result.map((item) => {
                    const hint = new vscode.InlayHint(position(item.position), item.label, item.kind === 2 ? 2 : 1);
                    hint.paddingLeft = !!item.paddingLeft;
                    return hint;
                });
            },
        }),
        vscode.languages.registerDocumentSemanticTokensProvider(selector, {
            onDidChangeSemanticTokens: results.event,
            async provideDocumentSemanticTokens(doc, token) {
                const version = doc.version;
                const result = await ask('textDocument/semanticTokens/full', { textDocument: document(doc) }, token);
                if (!result?.data || doc.version !== version) return null;
                return new vscode.SemanticTokens(new Uint32Array(result.data));
            },
        }, new vscode.SemanticTokensLegend(tokenTypes, tokenModifiers)),
        vscode.languages.registerCodeActionsProvider(selector, {
            async provideCodeActions(doc, wanted, context, token) {
                const ours = context.diagnostics.filter((d) => d.source === 'dewy-core');
                if (ours.length === 0) return [];
                const version = doc.version;
                const result = await ask('textDocument/codeAction', {
                    textDocument: document(doc), range: lspRange(wanted),
                    context: { diagnostics: ours.map((d) => ({ range: lspRange(d.range), message: d.message,
                        severity: d.severity + 1, source: d.source })) },
                }, token);
                if (!result || doc.version !== version) return [];
                return result.map((item) => {
                    const action = new vscode.CodeAction(item.title, vscode.CodeActionKind.QuickFix);
                    action.edit = edit(item.edit);
                    action.isPreferred = !!item.isPreferred;
                    const fixes = (item.diagnostics || []).map((d) => d.message);
                    action.diagnostics = ours.filter((d) => fixes.includes(d.message));
                    return action;
                });
            },
        }, { providedCodeActionKinds: [vscode.CodeActionKind.QuickFix] }),
        vscode.languages.registerWorkspaceSymbolProvider({
            async provideWorkspaceSymbols(query, token) {
                const result = await ask('workspace/symbol', { query }, token);
                return (result || []).map((item) => new vscode.SymbolInformation(item.name, item.kind - 1,
                    item.containerName || '', location(item.location)));
            },
        }),
        vscode.languages.registerCodeLensProvider(selector, {
            onDidChangeCodeLenses: results.event,
            async provideCodeLenses(doc, token) {
                const version = doc.version;
                const result = await ask('textDocument/codeLens', { textDocument: document(doc) }, token);
                if (!result || doc.version !== version) return null;
                return result.map((item) => new vscode.CodeLens(range(item.range), {
                    title: item.command.title, command: item.command.command,
                    arguments: (item.command.arguments || []).map((value, index) => index === 0 ? vscode.Uri.parse(value) : value),
                }));
            },
        }),
        vscode.commands.registerCommand('dewy.core.restartServer', restart),
        vscode.workspace.onDidChangeConfiguration((event) => {
            if (event.affectsConfiguration('dewy.core.path')) restart();
        }),
        vscode.workspace.onDidGrantWorkspaceTrust(start),
        vscode.workspace.onDidChangeWorkspaceFolders(restart),
    );
    active = { dispose() {
        disposed = true;
        clearTimeout(restartTimer);
        const old = client;
        client = null;
        old?.stop();
    } };
    context.subscriptions.push(active);
    start();
}

function deactivate() { active?.dispose(); active = null; }
module.exports = { activate, deactivate };
