// Run the standalone compiler through editor-owned, cancellable process tasks.
const path = require('node:path');

function activate(context, vscode) {
    const run = async (release, watch = false) => {
        const document = vscode.window.activeTextEditor?.document;
        if (!document || document.languageId !== 'dewy' || document.uri.scheme !== 'file') return;
        try {
            if (!vscode.workspace.isTrusted) throw new Error('Trust this workspace before running tests.');
            const compiler = vscode.workspace.getConfiguration('dewy', document.uri).get('core.path', '').trim();
            if (!compiler) throw new Error('Set dewy.core.path to the compiler or checkout tools/dewy launcher.');
            if (!await vscode.workspace.saveAll(false)) return;
            const source = document.uri.fsPath;
            const args = ['test', ...(watch ? ['--watch'] : []), ...(release ? ['--release'] : []), source];
            const execution = new vscode.ProcessExecution(compiler, args, { cwd: path.dirname(source) });
            const folder = vscode.workspace.getWorkspaceFolder(document.uri);
            const task = new vscode.Task(
                { type: 'process', command: compiler, args }, folder || vscode.TaskScope.Workspace,
                `${watch ? 'Watch tests in' : 'Test'} ${path.basename(source)}${release ? ' (release)' : ''}`,
                'Dewy', execution, ['$gcc'],
            );
            task.group = vscode.TaskGroup.Test;
            task.presentationOptions = {
                reveal: vscode.TaskRevealKind.Always, panel: vscode.TaskPanelKind.Shared, clear: true,
            };
            await vscode.tasks.executeTask(task);
        } catch (error) {
            vscode.window.showErrorMessage(`Dewy core: ${error.message}`);
        }
    };
    context.subscriptions.push(
        vscode.commands.registerCommand('dewy.core.test', () => run(false)),
        vscode.commands.registerCommand('dewy.core.testRelease', () => run(true)),
        vscode.commands.registerCommand('dewy.core.testWatch', () => run(false, true)),
    );
}

module.exports = { activate };
