// Exercise the real debug build/discovery process behind the VS Code API boundary.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
const [extension, compiler, directory] = process.argv.slice(2);
const { splitArguments } = require(path.join(path.dirname(extension), 'extension.js'));
// Discovery must not find a compiler installed on this machine: only the configured one.
process.env.HOME = process.env.USERPROFILE = directory;
process.env.PATH = (process.env.PATH || '').split(path.delimiter)
    .filter((d) => !['dewy-core', 'dewy-core.exe', 'dewy-core.cmd'].some((n) => fs.existsSync(path.join(d, n))))
    .join(path.delimiter);
const source = path.join(directory, 'source with spaces.dewy');
const compilerLink = path.join(directory, 'compiler with spaces');
fs.symlinkSync(compiler, compilerLink);
fs.writeFileSync(source, 'main=()=>unknown_on_disk');
let body = 'main=():>void=>exit(42)';
let setting = compilerLink;
let save = true;
let installed = true;
let provider, terminate;
const commands = new Map();
const errors = [];
const log = [];
const starts = [];
const disposable = { dispose() {} };
const folder = { uri: { scheme: 'file', fsPath: directory } };
const document = { languageId: 'dewy', uri: { scheme: 'file', fsPath: source } };
const vscode = {
    window: {
        activeTextEditor: { document },
        createOutputChannel: () => ({ ...disposable, append: (s) => log.push(s), appendLine: (s) => log.push(s), show() {} }),
        showErrorMessage: (s) => errors.push(s),
    },
    workspace: {
        isTrusted: false,
        getConfiguration: () => ({ get: () => setting }),
        getWorkspaceFolder: () => folder,
        saveAll: async (includeUntitled) => {
            assert.equal(includeUntitled, false);
            if (save) fs.writeFileSync(source, body);
            return save;
        },
    },
    extensions: { getExtension: () => installed ? {} : undefined },
    commands: { registerCommand: (name, fn) => { commands.set(name, fn); return disposable; } },
    debug: {
        registerDebugConfigurationProvider: (type, p) => { assert.equal(type, 'dewy-core'); provider = p; return disposable; },
        onDidTerminateDebugSession: (fn) => { terminate = fn; return disposable; },
        startDebugging: async (f, config) => { starts.push({ f, config }); return true; },
    },
};
const context = { subscriptions: [] };
const config = { type: 'dewy-core', request: 'launch', name: 'test', program: source,
    args: '"two words" \'\' \'$literal\'', env: { GREETING: 'hello' } };
const resolve = (c = config) => provider.resolveDebugConfigurationWithSubstitutedVariables(folder, c);
(async () => {
    try {
        require(extension).activate(context, vscode, splitArguments);
        assert.equal(await resolve(), undefined);
        assert.match(errors.at(-1), /Trust/);
        vscode.workspace.isTrusted = true;
        setting = '';
        assert.equal(await resolve(), undefined);
        assert.match(errors.at(-1), /core.path/);
        setting = compilerLink;
        installed = false;
        assert.equal(await resolve(), undefined);
        assert.match(errors.at(-1), /CodeLLDB/);
        installed = true;
        assert.equal(await resolve({ ...config, args: '"unclosed' }), undefined);
        assert.match(errors.at(-1), /unbalanced/);
        save = false;
        assert.equal(await resolve(), undefined);
        assert(!log.some((line) => line.startsWith('Building')));
        save = true;
        const built = await resolve();
        assert(built, log.join(''));
        assert.equal(built.type, 'lldb');
        assert.deepEqual(built.args, ['two words', '', '$literal']);
        assert.deepEqual(built.env, { GREETING: 'hello' });
        assert.equal(built.cwd, directory);
        assert(built.initCommands.some((line) => line.includes('dewy_lldb.py')));
        assert(built.initCommands.some((line) => line.includes('__panic')));
        assert.equal(cp.spawnSync(built.program).status, 42);
        const lib = cp.execFileSync(compiler, ['--print-lib'], { encoding: 'utf8' }).trim();
        fs.symlinkSync(lib, path.join(directory, 'runtime files'));
        process.env.DEWY_CORE_LIB = 'runtime files';
        const second = await resolve({ ...config, stopOnPanic: false });
        assert(second && second.program !== built.program);
        assert(second.initCommands.some((line) => line.includes('runtime files')));
        assert(!second.initCommands.some((line) => line.includes('__panic')));
        assert(fs.existsSync(built.program), 'a second build replaced a running executable');
        terminate({ configuration: built });
        assert(!fs.existsSync(built.program));
        assert(fs.existsSync(second.program));
        body = 'main=()=>unknown_in_debug_build';
        assert.equal(await resolve(), undefined);
        assert.match(log.join(''), /unknown_in_debug_build/);
        assert.deepEqual(fs.readdirSync(process.env.TMPDIR), [path.basename(path.dirname(second.program))]);
        assert.equal(provider.provideDebugConfigurations()[0].program, '${file}');
        assert.equal(provider.resolveDebugConfiguration(folder, {}).program, source);
        await commands.get('dewy.core.debug')();
        assert.equal(starts[0].config.program, source);
        assert.equal(starts[0].f, folder);
        for (const item of context.subscriptions.reverse()) item.dispose();
        assert(!fs.existsSync(second.program));
        console.log('debug builds, arguments, failures and cleanup passed');
    } finally {
        for (const item of context.subscriptions) item.dispose();
    }
})().catch((error) => { console.error(error); process.exitCode = 1; });
