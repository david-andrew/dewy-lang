// Run the standalone compiler through editor-owned, cancellable process tasks.
const path = require('node:path');
const { compilerFor, missing } = require('./compiler');

function activate(context, vscode) {
    // The document to run: the one a code lens names, else the active editor's.
    const target = (uri) => {
        if (uri && typeof uri === 'object' && uri.fsPath) {
            return vscode.workspace.textDocuments?.find((doc) => doc.uri.toString() === uri.toString())
                || { languageId: 'dewy', uri };
        }
        return vscode.window.activeTextEditor?.document;
    };
    const run = async (uri, options) => {
        const document = target(uri);
        if (!document || document.languageId !== 'dewy' || document.uri.scheme !== 'file') return;
        try {
            if (!vscode.workspace.isTrusted) throw new Error(`Trust this workspace before ${options.test ? 'running tests' : 'running programs'}.`);
            const compiler = compilerFor(vscode, document.uri);
            if (!compiler) throw new Error(missing);
            if (!await vscode.workspace.saveAll(false)) return;
            const source = document.uri.fsPath;
            const args = options.test
                ? ['test', ...(options.watch ? ['--watch'] : []), ...(options.release ? ['--release'] : []), source, ...(options.filters || [])]
                : ['run', source];
            const execution = new vscode.ProcessExecution(compiler, args, { cwd: path.dirname(source) });
            const folder = vscode.workspace.getWorkspaceFolder(document.uri);
            const what = options.test
                ? `${options.watch ? 'Watch tests in' : 'Test'} ${path.basename(source)}${options.filters ? ` (${options.filters.join(' ')})` : ''}${options.release ? ' (release)' : ''}`
                : `Run ${path.basename(source)}`;
            const task = new vscode.Task(
                { type: 'process', command: compiler, args }, folder || vscode.TaskScope.Workspace,
                what, 'Dewy', execution, ['$gcc'],
            );
            if (options.test) task.group = vscode.TaskGroup.Test;
            task.presentationOptions = {
                reveal: vscode.TaskRevealKind.Always, panel: vscode.TaskPanelKind.Shared, clear: true,
            };
            await vscode.tasks.executeTask(task);
        } catch (error) {
            vscode.window.showErrorMessage(`Dewy core: ${error.message}`);
        }
    };
    context.subscriptions.push(
        vscode.commands.registerCommand('dewy.core.test', (uri) => run(uri, { test: true })),
        vscode.commands.registerCommand('dewy.core.testRelease', (uri) => run(uri, { test: true, release: true })),
        vscode.commands.registerCommand('dewy.core.testWatch', (uri) => run(uri, { test: true, watch: true })),
        vscode.commands.registerCommand('dewy.core.runTest', (uri, name) => run(uri, { test: true, filters: [name] })),
        vscode.commands.registerCommand('dewy.core.run', (uri) => run(uri, {})),
    );
}

module.exports = { activate };
