// Which compiler the extension runs, in order: the `dewy.core.path` setting; the toolchain bundled
// in this platform's package (toolchain/bin/dewy-core beside its lib/); the installer's launcher
// (~/.dewy/bin/dewy-core); dewy-core on the PATH. Nothing is downloaded.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const windows = process.platform === 'win32';
let extensionPath = null;

const isFile = (candidate) => {
    try { return fs.statSync(candidate).isFile(); } catch { return false; }
};

function bundled() {
    if (!extensionPath) return null;
    const candidate = path.join(extensionPath, 'toolchain', 'bin', windows ? 'dewy-core.exe' : 'dewy-core');
    if (!isFile(candidate)) return null;
    // (an archive that dropped the executable bit)
    if (!windows) {
        try { fs.accessSync(candidate, fs.constants.X_OK); } catch {
            try { fs.chmodSync(candidate, 0o755); } catch { return null; }
        }
    }
    return candidate;
}

function installed() {
    const home = process.env.USERPROFILE && windows ? process.env.USERPROFILE : os.homedir();
    const candidate = path.join(home, '.dewy', 'bin', windows ? 'dewy-core.cmd' : 'dewy-core');
    return isFile(candidate) ? candidate : null;
}

function onPath() {
    const names = windows ? ['dewy-core.exe', 'dewy-core.cmd'] : ['dewy-core'];
    for (const directory of (process.env.PATH || '').split(path.delimiter)) {
        if (!directory) continue;
        for (const name of names) {
            const candidate = path.join(directory, name);
            if (isFile(candidate)) return candidate;
        }
    }
    return null;
}

// The compiler for resource (a document or folder URI), or '' when there is none.
function compilerFor(vscode, resource) {
    const configured = vscode.workspace.getConfiguration('dewy', resource).get('core.path', '');
    return (configured || '').trim() || bundled() || installed() || onPath() || '';
}

// child_process arguments for running command: Windows runs a .cmd launcher through its shell.
function processCommand(command, args, options = {}) {
    if (windows && /\.(cmd|bat)$/i.test(command)) {
        const quote = (s) => `"${String(s).replace(/"/g, '""')}"`;
        return [quote(command), args.map(quote), { ...options, shell: true }];
    }
    return [command, args, options];
}

const missing = 'No Dewy compiler: install Dewy, use a platform build of the extension, or set dewy.core.path to the compiler or a checkout\'s tools/dewy launcher.';

module.exports = {
    compilerFor,
    processCommand,
    missing,
    setExtensionPath(value) { extensionPath = value || null; },
};
