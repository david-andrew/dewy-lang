// The extension's compiler discovery order, with the file system and environment as doubles.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const [compiler, directory] = process.argv.slice(2);
const windows = process.platform === 'win32';
const home = path.join(directory, 'home');
const pathDirectory = path.join(directory, 'path bin');
const extension = path.join(directory, 'extension');
process.env.HOME = process.env.USERPROFILE = home;
process.env.PATH = pathDirectory;
const discovery = require(compiler);
let setting = '';
const vscode = { workspace: { getConfiguration: (section) => {
    assert.equal(section, 'dewy');
    return { get: (key) => { assert.equal(key, 'core.path'); return setting; } };
} } };
const touch = (file) => { fs.mkdirSync(path.dirname(file), { recursive: true }); fs.writeFileSync(file, ''); return file; };
discovery.setExtensionPath(extension);
assert.equal(discovery.compilerFor(vscode), '');
const onPath = touch(path.join(pathDirectory, windows ? 'dewy-core.exe' : 'dewy-core'));
assert.equal(discovery.compilerFor(vscode), onPath);
const installed = touch(path.join(home, '.dewy', 'bin', windows ? 'dewy-core.cmd' : 'dewy-core'));
assert.equal(discovery.compilerFor(vscode), installed);
const bundled = touch(path.join(extension, 'toolchain', 'bin', windows ? 'dewy-core.exe' : 'dewy-core'));
assert.equal(discovery.compilerFor(vscode), bundled);
if (!windows) assert.notEqual(fs.statSync(bundled).mode & 0o111, 0, 'the bundled compiler is made executable');
setting = '  /configured/dewy-core ';
assert.equal(discovery.compilerFor(vscode), '/configured/dewy-core');
const [file, args, options] = discovery.processCommand('C:\\Program Files\\dewy-core.cmd', ['lsp', 'a b'], { cwd: directory });
if (windows) {
    assert.equal(options.shell, true);
    assert.deepEqual([file, args], ['"C:\\Program Files\\dewy-core.cmd"', ['"lsp"', '"a b"']]);
} else {
    assert.deepEqual([file, args, options], ['C:\\Program Files\\dewy-core.cmd', ['lsp', 'a b'], { cwd: directory }]);
}
console.log('compiler discovery: setting, bundled, installed and PATH passed');
