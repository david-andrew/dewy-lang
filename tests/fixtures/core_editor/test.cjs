// Execute the task's actual process behind a small VS Code API double.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
const [extension, compiler, directory] = process.argv.slice(2);
const compilerLink = path.join(directory, 'compiler with spaces');
fs.symlinkSync(compiler, compilerLink);
const source = path.join(directory, 'tests & $literal.dewy');
fs.writeFileSync(source, 'test "old disk version" { assert(false) }');
let body = 'test "saved version" { assert(true) }';
let setting = compilerLink;
let save = true;
let taskError = false;
const errors = [];
const tasks = [];
const results = [];
const commands = new Map();
const disposable = { dispose() {} };
const folder = { uri: { scheme: 'file', fsPath: directory } };
const document = { languageId: 'dewy', uri: { scheme: 'file', fsPath: source } };
const vscode = {
    window: { activeTextEditor: { document }, showErrorMessage: (s) => errors.push(s) },
    workspace: {
        isTrusted: false,
        getConfiguration: (section, resource) => {
            assert.equal(section, 'dewy'); assert.equal(resource, document.uri);
            return { get: (key) => { assert.equal(key, 'core.path'); return setting; } };
        },
        getWorkspaceFolder: () => folder,
        saveAll: async (untitled) => {
            assert.equal(untitled, false);
            if (save) fs.writeFileSync(source, body);
            return save;
        },
    },
    commands: { registerCommand: (name, fn) => { commands.set(name, fn); return disposable; } },
    ProcessExecution: class {
        constructor(process, args, options) { Object.assign(this, { process, args, options }); }
    },
    Task: class {
        constructor(definition, scope, name, source, execution, problemMatchers) {
            Object.assign(this, { definition, scope, name, source, execution, problemMatchers });
        }
    },
    TaskScope: { Workspace: 2 }, TaskGroup: { Test: 'test' },
    TaskRevealKind: { Always: 1 }, TaskPanelKind: { Shared: 1 },
    tasks: {
        executeTask: async (task) => {
            if (taskError) throw new Error('task unavailable');
            tasks.push(task);
            const { process, args, options } = task.execution;
            results.push(cp.spawnSync(process, args, { ...options, encoding: 'utf8', timeout: 15000 }));
            return { task, terminate() {} };
        },
    },
};
(async () => {
    const context = { subscriptions: [] };
    require(extension).activate(context, vscode);
    const run = commands.get('dewy.core.test');
    await run();
    assert.match(errors.at(-1), /Trust/);
    assert.equal(tasks.length, 0);
    vscode.workspace.isTrusted = true;
    setting = '';
    await run();
    assert.match(errors.at(-1), /core.path/);
    assert.equal(tasks.length, 0);
    setting = compilerLink;
    save = false;
    await run();
    assert.equal(tasks.length, 0);
    save = true;
    await run();
    assert.equal(results.at(-1).status, 0, results.at(-1).stderr);
    assert.match(results.at(-1).stdout, /test saved version .*ok/);
    assert.equal(tasks.at(-1).scope, folder);
    assert.equal(tasks.at(-1).group, vscode.TaskGroup.Test);
    assert.deepEqual(tasks.at(-1).execution.args, ['test', source]);
    assert.deepEqual(tasks.at(-1).problemMatchers, ['$gcc']);
    assert.equal(tasks.at(-1).execution.options.cwd, directory);
    await commands.get('dewy.core.testRelease')();
    assert.equal(results.at(-1).status, 0, results.at(-1).stderr);
    assert.deepEqual(tasks.at(-1).execution.args, ['test', '--release', source]);
    body = 'test "fails" { assert(false) }\ntest "still runs" { assert(true) }';
    await run();
    assert.notEqual(results.at(-1).status, 0);
    assert.match(results.at(-1).stdout, /test still runs .*ok/);
    vscode.workspace.getWorkspaceFolder = () => undefined;
    body = 'test "standalone file" { assert(true) }';
    await run();
    assert.equal(tasks.at(-1).scope, vscode.TaskScope.Workspace);
    assert.equal(results.at(-1).status, 0, results.at(-1).stderr);
    taskError = true;
    await run();
    assert.match(errors.at(-1), /task unavailable/);
    const count = tasks.length;
    document.uri.scheme = 'untitled';
    await run();
    assert.equal(tasks.length, count);
    for (const item of context.subscriptions) item.dispose();
    console.log('test tasks: saved sources, release mode, failures and literal paths passed');
})().catch((error) => { console.error(error); process.exitCode = 1; });
