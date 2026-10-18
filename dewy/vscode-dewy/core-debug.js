// Adapted from Sloppy's debug-provider workflow at d113c79.
// Copyright (c) 2026 David Samson. MIT; see THIRD_PARTY_NOTICES.md.
const cp = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { promisify } = require('node:util');
const execFile = promisify(cp.execFile);

function activate(context, vscode, splitArguments) {
    const output = vscode.window.createOutputChannel('Dewy Core Debug');
    const builds = new Set();
    const removeBuild = (directory) => {
        if (!builds.delete(directory)) return;
        try { fs.rmSync(directory, { recursive: true, force: true }); } catch { /* still in use */ }
    };
    const configuration = (program) => ({
        type: 'dewy-core', request: 'launch', name: `Dewy core: ${path.basename(program)}`, program,
    });
    const provider = {
        provideDebugConfigurations() { return [configuration('${file}')]; },
        resolveDebugConfiguration(_folder, config) {
            const editor = vscode.window.activeTextEditor;
            if (!config.type && !config.request && editor?.document.languageId === 'dewy') {
                return configuration(editor.document.uri.fsPath);
            }
            return config;
        },
        async resolveDebugConfigurationWithSubstitutedVariables(folder, config) {
            let directory;
            try {
                if (!vscode.workspace.isTrusted) throw new Error('Trust this workspace before debugging.');
                if (config.request !== 'launch') throw new Error('The core debugger supports launching a Dewy source file.');
                const compiler = vscode.workspace.getConfiguration('dewy', folder?.uri).get('core.path', '').trim();
                if (!compiler) throw new Error('Set dewy.core.path to the compiler or checkout tools/dewy launcher.');
                if (!config.program || !config.program.endsWith('.dewy')) throw new Error('The debug program must be a .dewy source file.');
                if (!vscode.extensions.getExtension('vadimcn.vscode-lldb')) throw new Error('Install the CodeLLDB extension to debug with the compact core.');
                const args = typeof config.args === 'string' ? splitArguments(config.args) : (config.args || []);
                if (!Array.isArray(args) || args.some((arg) => typeof arg !== 'string')) throw new Error('Debug arguments must be strings.');
                if (!await vscode.workspace.saveAll(false)) return undefined;
                const program = path.resolve(folder?.uri.fsPath || process.cwd(), config.program);
                const cwd = path.resolve(folder?.uri.fsPath || path.dirname(program), config.cwd || path.dirname(program));
                directory = fs.mkdtempSync(path.join(os.tmpdir(), 'dewy-core-debug-'));
                builds.add(directory);
                const binary = path.join(directory, 'program' + (process.platform === 'win32' ? '.exe' : ''));
                output.appendLine(`Building ${program} with variable information…`);
                const options = { cwd, timeout: 120000, maxBuffer: 8 * 1024 * 1024 };
                const built = await execFile(compiler, ['build', program, '-g', '-o', binary], options);
                output.append(built.stdout + built.stderr);
                // Ask the running compiler, so a development launcher and library
                // overrides resolve to the matching toolchain's formatters.
                const info = await execFile(compiler, ['--print-lib'], options);
                const lib = info.stdout.trim();
                const formatter = path.resolve(cwd, lib, 'debug', 'sloppy_lldb.py');
                if (!lib || !fs.existsSync(formatter)) throw new Error('The toolchain has no LLDB value formatter.');
                const initCommands = [`command script import ${JSON.stringify(formatter)}`];
                if (config.stopOnPanic !== false) initCommands.push('breakpoint set -n __panic');
                return {
                    type: 'lldb', request: 'launch', name: config.name, program: binary,
                    args, cwd, env: config.env, initCommands,
                };
            } catch (error) {
                if (directory) removeBuild(directory);
                output.appendLine(error.stderr || error.message);
                output.show(true);
                vscode.window.showErrorMessage(`Dewy core: ${error.stderr ? 'build failed; see Dewy Core Debug output.' : error.message}`);
                return undefined;
            }
        },
    };
    context.subscriptions.push(output,
        vscode.debug.registerDebugConfigurationProvider('dewy-core', provider),
        vscode.debug.onDidTerminateDebugSession((session) => {
            if (session.configuration.program) removeBuild(path.dirname(session.configuration.program));
        }),
        vscode.commands.registerCommand('dewy.core.debug', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor || editor.document.languageId !== 'dewy' || editor.document.uri.scheme !== 'file') return;
            const folder = vscode.workspace.getWorkspaceFolder(editor.document.uri);
            await vscode.debug.startDebugging(folder, configuration(editor.document.uri.fsPath));
        }),
        { dispose() { for (const directory of [...builds]) removeBuild(directory); } },
    );
}

module.exports = { activate };
