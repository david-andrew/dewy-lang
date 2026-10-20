// Dewy editor integration: the language client, debugging, run and test commands, and
// shell-style splitting of program arguments typed for a debug session.

let lastArguments = '';

// POSIX-style word splitting: whitespace separates, single quotes are
// literal, double quotes and backslashes escape (shlex.split in Python).
function splitArguments(line) {
    const words = [];
    let word = null;
    let quote = null;
    for (let i = 0; i < line.length; i++) {
        const c = line[i];
        if (quote === "'") {
            if (c === "'") quote = null; else word += c;
        } else if (quote === '"') {
            if (c === '"') quote = null;
            else if (c === '\\' && i + 1 < line.length && '"\\$`\n'.includes(line[i + 1])) word += line[++i];
            else word += c;
        } else if (c === "'" || c === '"') {
            quote = c;
            if (word === null) word = '';
        } else if (c === '\\' && i + 1 < line.length) {
            word = (word ?? '') + line[++i];
        } else if (/\s/.test(c)) {
            if (word !== null) words.push(word);
            word = null;
        } else {
            word = (word ?? '') + c;
        }
    }
    if (quote !== null) throw new Error('unbalanced quotes in the program arguments');
    if (word !== null) words.push(word);
    return words;
}

function activate(context) {
    const vscode = require('vscode');
    require('./compiler').setExtensionPath(context.extensionPath);
    require('./core-client').activate(context, vscode);
    require('./core-debug').activate(context, vscode, splitArguments);
    require('./core-test').activate(context, vscode);
    context.subscriptions.push(vscode.commands.registerCommand('dewy.programArguments', async () => {
        const typed = await vscode.window.showInputBox({
            prompt: 'Command-line arguments for the program (split like a shell)',
            value: lastArguments,
            valueSelection: [0, lastArguments.length],
            ignoreFocusOut: true,
        });
        if (typed === undefined) {
            return undefined;   // Escape: the launch is cancelled
        }
        lastArguments = typed;
        return typed;
    }));
}

function deactivate() { require('./core-client').deactivate(); }

module.exports = { activate, deactivate, splitArguments };
