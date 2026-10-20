// VS Code API boundary doubles; requests and diagnostics use the real native LSP.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL, fileURLToPath } = require('node:url');
const cp = require('node:child_process');
let spawned = 0;
const spawn = cp.spawn;
cp.spawn = (...args) => { spawned++; return spawn(...args); };
const [extension, compiler, directory] = process.argv.slice(2);
const client = require(extension);
// Discovery must not find a compiler installed on this machine: only the configured one.
process.env.HOME = process.env.USERPROFILE = directory;
process.env.PATH = (process.env.PATH || '').split(path.delimiter)
    .filter((d) => !['dewy-core', 'dewy-core.exe', 'dewy-core.cmd'].some((n) => fs.existsSync(path.join(d, n))))
    .join(path.delimiter);
let setting = '';
let body = '# 🙂\nlet answer:int64=42\nmain=()=>answer';
const disk = 'main=()=>missing_on_disk';
const source = path.join(directory, 'editor.dewy');
fs.writeFileSync(source, disk);
const events = new Map();
const on = (name) => (callback) => {
    const callbacks = events.get(name) || new Set();
    callbacks.add(callback); events.set(name, callbacks);
    return { dispose: () => callbacks.delete(callback) };
};
const fire = (name, value) => { for (const callback of events.get(name) || []) callback(value); };
const uri = (text) => ({ scheme: 'file', fsPath: fileURLToPath(text), toString: () => text });
const document = { uri: uri(pathToFileURL(source).href), languageId: 'dewy', version: 1, getText: () => body };
const values = new Map();
const notices = [];
const log = [];
const commands = new Map();
const providers = {};
const disposable = { dispose() {} };
class Position { constructor(line, character) { Object.assign(this, { line, character }); } }
class Range { constructor(start, end) { Object.assign(this, { start, end }); } }
class Location { constructor(uri, range) { Object.assign(this, { uri, range }); } }
class Diagnostic { constructor(range, message, severity) { Object.assign(this, { range, message, severity }); } }
class MarkdownString { constructor(value) { this.value = value; } }
class Hover { constructor(contents) { this.contents = contents; } }
class CompletionItem { constructor(label, kind) { Object.assign(this, { label, kind }); } }
class CompletionList { constructor(items, isIncomplete) { Object.assign(this, { items, isIncomplete }); } }
class TextEdit { constructor(range, newText) { Object.assign(this, { range, newText }); } }
class DocumentHighlight { constructor(range, kind) { Object.assign(this, { range, kind }); } }
class EventEmitter {
    constructor() { this.listeners = new Set(); this.event = (fn) => { this.listeners.add(fn); return { dispose: () => this.listeners.delete(fn) }; }; }
    fire(value) { for (const fn of this.listeners) fn(value); }
    dispose() { this.listeners.clear(); }
}
class WorkspaceEdit {
    constructor() { this.edits = []; }
    replace(uri, range, newText) { this.edits.push({ uri: uri.toString(), range, newText }); }
}
class SignatureHelp {}
class SignatureInformation { constructor(label, documentation) { Object.assign(this, { label, documentation, parameters: [] }); } }
class ParameterInformation { constructor(label) { this.label = label; } }
class InlayHint { constructor(position, label, kind) { Object.assign(this, { position, label, kind }); } }
class SemanticTokens { constructor(data) { this.data = data; } }
class SemanticTokensLegend { constructor(tokenTypes, tokenModifiers) { Object.assign(this, { tokenTypes, tokenModifiers }); } }
class CodeAction { constructor(title, kind) { Object.assign(this, { title, kind }); } }
class SymbolInformation { constructor(name, kind, containerName, location) { Object.assign(this, { name, kind, containerName, location }); } }
class CodeLens { constructor(range, command) { Object.assign(this, { range, command }); } }
class DocumentSymbol {
    constructor(name, detail, kind, range, selectionRange) {
        Object.assign(this, { name, detail, kind, range, selectionRange });
    }
}
const vscode = {
    Position, Range, Location, Diagnostic, MarkdownString, Hover, CompletionItem, CompletionList, TextEdit, DocumentHighlight, DocumentSymbol, Uri: { parse: uri },
    EventEmitter, WorkspaceEdit, SignatureHelp, SignatureInformation, ParameterInformation, InlayHint, SemanticTokens,
    SemanticTokensLegend, CodeAction, CodeActionKind: { QuickFix: 'quickfix' }, SymbolInformation, CodeLens,
    window: { createOutputChannel: () => ({ ...disposable, append: (s) => log.push(s), appendLine: (s) => log.push(s) }) },
    languages: {
        createDiagnosticCollection: () => ({
            ...disposable,
            set: (u, ds) => { values.set(u.toString(), ds); notices.push(ds); },
            clear: () => values.clear(), delete: (u) => values.delete(u.toString()),
        }),
        registerHoverProvider: (_selector, p) => { providers.hover = p; return disposable; },
        registerDefinitionProvider: (_selector, p) => { providers.definition = p; return disposable; },
        registerReferenceProvider: (_selector, p) => { providers.references = p; return disposable; },
        registerDocumentHighlightProvider: (_selector, p) => { providers.highlights = p; return disposable; },
        registerDocumentSymbolProvider: (_selector, p) => { providers.symbols = p; return disposable; },
        registerDocumentFormattingEditProvider: (_selector, p) => { providers.formatting = p; return disposable; },
        registerCompletionItemProvider: (_selector, p, ...triggers) => {
            assert.deepEqual(triggers, ['.', '$', '/', '"']); providers.completion = p; return disposable;
        },
        registerRenameProvider: (_selector, p) => { providers.rename = p; return disposable; },
        registerSignatureHelpProvider: (_selector, p, metadata) => {
            assert.deepEqual(metadata.triggerCharacters, ['(']); providers.signature = p; return disposable;
        },
        registerInlayHintsProvider: (_selector, p) => { providers.inlay = p; return disposable; },
        registerDocumentSemanticTokensProvider: (_selector, p, legend) => {
            providers.semantic = p; providers.legend = legend; return disposable;
        },
        registerCodeActionsProvider: (_selector, p) => { providers.actions = p; return disposable; },
        registerWorkspaceSymbolProvider: (p) => { providers.workspaceSymbols = p; return disposable; },
        registerCodeLensProvider: (_selector, p) => { providers.lenses = p; return disposable; },
    },
    commands: { registerCommand: (name, fn) => { commands.set(name, fn); return disposable; } },
    workspace: {
        isTrusted: false,
        workspaceFolders: [{ uri: uri(pathToFileURL(directory).href), name: 'editor test' }],
        textDocuments: [document], getConfiguration: () => ({ get: () => setting }),
        createFileSystemWatcher: () => ({ ...disposable, onDidCreate: on('create'), onDidChange: on('disk'), onDidDelete: on('delete') }),
        onDidOpenTextDocument: on('open'), onDidChangeTextDocument: on('change'), onDidCloseTextDocument: on('close'),
        onDidSaveTextDocument: on('save'), onDidChangeConfiguration: on('configuration'),
        onDidGrantWorkspaceTrust: on('trust'), onDidChangeWorkspaceFolders: on('folders'),
    },
};
const context = { subscriptions: [] };
async function until(predicate) {
    const deadline = Date.now() + 8000;
    while (!predicate()) {
        assert(Date.now() < deadline, `Timed out; diagnostics: ${JSON.stringify(notices)}; log: ${log.join('')}`);
        await new Promise((resolve) => setTimeout(resolve, 10));
    }
}
async function change(text, predicate) {
    body = text;
    document.version++;
    const seen = notices.length;
    fire('change', { document, contentChanges: [{ text }] });
    await until(() => notices.length > seen && predicate(notices.at(-1)));
}
(async () => {
    try {
        client.activate(context, vscode);
        assert.equal(spawned, 0);
        setting = compiler;
        fire('configuration', { affectsConfiguration: () => true });
        assert.equal(spawned, 0, 'untrusted workspace started a compiler');
        vscode.workspace.isTrusted = true;
        fire('trust');
        await until(() => notices.length > 0);
        assert.deepEqual(notices.at(-1), [], 'did not check the unsaved snapshot');
        const hover = await providers.hover.provideHover(document, new Position(2, 9));
        assert.match(hover.contents.value, /int|i64/);
        const definitions = await providers.definition.provideDefinition(document, new Position(2, 9));
        assert.equal((Array.isArray(definitions) ? definitions[0] : definitions).range.start.line, 1);
        const references = (includeDeclaration, token) => providers.references.provideReferences(
            document, new Position(2, 9), { includeDeclaration }, token);
        const refs = await references(true);
        assert.deepEqual(refs.map((item) => item.range.start.line), [1, 2]);
        assert(refs.every((item) => item.uri.toString() === document.uri.toString()));
        assert.deepEqual((await references(false)).map((item) => item.range.start.line), [2]);
        assert.equal(await references(true, { isCancellationRequested: true }), null);
        const highlights = () => providers.highlights.provideDocumentHighlights(document, new Position(2, 9));
        const occurrences = await highlights();
        assert.deepEqual(occurrences.map((item) => item.range), refs.map((item) => item.range));
        assert(occurrences.every((item) => item.kind === 0)); // VS Code Text
        const symbols = () => providers.symbols.provideDocumentSymbols(document);
        const outline = await symbols();
        assert.deepEqual(outline.map((item) => [item.name, item.kind]), [['answer', 12], ['main', 11]]);
        assert.deepEqual(outline[0].selectionRange, refs[0].range);
        const staleSymbols = symbols();
        document.version++;
        assert.equal(await staleSymbols, null);
        const staleHighlights = highlights();
        document.version++;
        assert.equal(await staleHighlights, null);
        const names = await providers.completion.provideCompletionItems(document, new Position(2, 15));
        const answer = names.items.find((item) => item.label === 'answer');
        assert.equal(answer.detail, 'int64');
        assert.equal(answer.kind, 5); // VS Code Variable
        assert(names.items.some((item) => item.label === 'printl'));
        assert(!names.items.some((item) => item.label === 'struct'));
        const format = () => providers.formatting.provideDocumentFormattingEdits(document, { tabSize: 4, insertSpaces: true });
        const edits = await format();
        assert.equal(edits.length, 1);
        assert.equal(edits[0].newText, '# 🙂\nlet answer: int64 = 42\nmain = () => answer\n');
        assert.equal(edits[0].range.end.character, 15);
        const stale = format();
        document.version++;
        assert.equal(await stale, null, 'formatting an old document version must not replace newer edits');
        const helperSource = path.join(directory, 'helper.dewy');
        const helperDisk = 'offset=(amount:int64)=>amount+2';
        fs.writeFileSync(helperSource, helperDisk);
        const helper = {
            uri: uri(pathToFileURL(helperSource).href), languageId: 'dewy', version: 1,
            getText: () => 'offset=(amount:int64)=>amount+3',
        };
        vscode.workspace.textDocuments.push(helper);
        fire('open', helper);
        await until(() => values.has(helper.uri.toString()));
        assert.deepEqual(values.get(helper.uri.toString()), []);
        await change('from p"helper.dewy" import offset\nmain=()=>offset(amount=39)', (ds) => ds.length === 0);
        const parameterRefs = await providers.references.provideReferences(
            helper, new Position(0, 9), { includeDeclaration: false });
        assert.equal(parameterRefs.length, 2);
        const namedArgument = parameterRefs.find((item) => item.uri.toString() === document.uri.toString());
        assert.deepEqual(namedArgument.range, new Range(new Position(1, 16), new Position(1, 22)));
        vscode.workspace.textDocuments = [document];
        fire('close', helper);
        assert.equal(fs.readFileSync(helperSource, 'utf8'), helperDisk);
        await change('main=()=>{let point=[x=42 y=1] return point.x}', (ds) => ds.length === 0);
        const fields = await providers.completion.provideCompletionItems(document, new Position(0, body.lastIndexOf('.x') + 1));
        assert.equal(fields.items.find((item) => item.label === 'x').kind, 4); // VS Code Field
        assert.equal(fields.items.find((item) => item.label === 'y').detail, 'int');
        // Signature help, rename, semantic tokens, inlay hints, quick fixes, symbols and lenses.
        await change('scale=(value:int64 factor:int64):>int64=>value*factor\nmain=():>int64=>{\n    let doubled=scale(21 2)\n    return doubled\n}\ntest "scales" { assert(scale(1 2) =? 2) }', (ds) => ds.length === 0);
        const help = await providers.signature.provideSignatureHelp(document, new Position(2, 25));
        assert.equal(help.signatures[0].label, 'scale = (value: int64 factor: int64):>int64');
        assert.equal(help.activeParameter, 1);
        assert.deepEqual(help.signatures[0].parameters.map((p) => p.label), [[9, 21], [22, 35]]);
        const renamed = await providers.rename.provideRenameEdits(document, new Position(2, 18), 'times');
        assert.deepEqual(renamed.edits.map((e) => [e.range.start.line, e.newText]).sort(), [[0, 'times'], [2, 'times'], [5, 'times']]);
        assert(await providers.rename.prepareRename(document, new Position(2, 18)));
        await assert.rejects(providers.rename.provideRenameEdits(document, new Position(2, 18), 'doubled'), /declared already/);
        const tokens = await providers.semantic.provideDocumentSemanticTokens(document);
        assert(tokens.data instanceof Uint32Array && tokens.data.length % 5 === 0 && tokens.data.length > 0);
        assert.equal(providers.legend.tokenTypes[tokens.data[3]], 'function');
        const hints = await providers.inlay.provideInlayHints(document, new Range(new Position(0, 0), new Position(9, 0)));
        assert.deepEqual(hints.map((h) => [h.position.line, h.label, h.kind]), [[2, ': int64', 1]]);
        const found = await providers.workspaceSymbols.provideWorkspaceSymbols('scal');
        assert(found.some((s) => s.name === 'scale' && s.kind === 11));
        const lenses = await providers.lenses.provideCodeLenses(document);
        assert.deepEqual(lenses.map((l) => [l.range.start.line, l.command.command]),
            [[1, 'dewy.core.run'], [1, 'dewy.core.debug'], [5, 'dewy.core.test'], [5, 'dewy.core.runTest']]);
        assert.equal(lenses[3].command.arguments[0].toString(), document.uri.toString());
        assert.equal(lenses[3].command.arguments[1], 'scales');
        await change('double=(x:int64):>int64=>x*2\nmain=():>int64=>{\n    let xs:array<int64>=[1]\n    return xs.map(double)[0]\n}', (ds) => ds.length > 0);
        const bad = values.get(document.uri.toString());
        const actions = await providers.actions.provideCodeActions(document, bad[0].range, { diagnostics: bad });
        assert.equal(actions.length, 1);
        assert.equal(actions[0].title, 'Write `@double` for the function itself');
        assert.deepEqual(actions[0].edit.edits.map((e) => e.newText), ['@']);
        assert.deepEqual(actions[0].diagnostics, [bad[0]]);
        await change('# 🙂\nmain=()=>unknown_editor', (ds) => ds.some((d) => d.message.includes('unknown_editor')));
        assert.equal(notices.at(-1)[0].range.start.line, 1);
        await change('main=()=>{', (ds) => ds.length > 0 && !ds[0].message.includes('unknown_editor'));
        assert.deepEqual(await format(), []);
        await change('main=()=>42', (ds) => ds.length === 0);
        const seen = notices.length;
        commands.get('dewy.core.restartServer')();
        await until(() => notices.length > seen);
        assert.deepEqual(notices.at(-1), []);
        assert.equal(spawned, 2);
        vscode.workspace.textDocuments = [];
        fire('close', document);
        assert(!values.has(document.uri.toString()));
        setting = '';
        fire('configuration', { affectsConfiguration: () => true });
        assert.equal(spawned, 2);
        assert.equal(await providers.hover.provideHover(document, new Position(0, 0)), null);
        assert.equal(await providers.completion.provideCompletionItems(document, new Position(0, 0)), null);
        assert.equal(await format(), null);
        assert.equal(await references(true), null);
        assert.equal(await highlights(), null);
        assert.equal(await symbols(), null);
        assert.equal(fs.readFileSync(source, 'utf8'), disk, 'editor integration modified the file');
        console.log('core editor: opt-in, trust, snapshots, diagnostics, hover, definition, completion, restart and close passed');
    } finally {
        client.deactivate();
        for (const item of context.subscriptions.reverse()) item.dispose();
    }
})().catch((error) => { console.error(error); process.exitCode = 1; });
