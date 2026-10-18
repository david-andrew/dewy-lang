// Exercise running checker cancellation on every native host, using framed LSP directly.
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const {pathToFileURL} = require('node:url');
const path = require('node:path');
const [compiler, directory] = process.argv.slice(2);
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const frame = message => {
    const body = Buffer.from(JSON.stringify({jsonrpc: '2.0', ...message}));
    return Buffer.concat([Buffer.from(`Content-Length: ${body.length}\r\n\r\n`), body]);
};
const uri = pathToFileURL(path.join(directory, 'counter with spaces.dewy')).href;
const text = 'answer=42\nmain=()=>{ return answer }\n';
const document = {textDocument: {uri}, position: {line: 1, character: 22}};
const opened = () => ({method: 'textDocument/didOpen', params: {
    textDocument: {uri, languageId: 'dewy', version: 1, text},
}});
const changed = version => ({method: 'textDocument/didChange', params: {
    textDocument: {uri, version}, contentChanges: [{text}],
}});

class Client {
    constructor() {
        this.process = spawn(compiler, ['lsp'], {
            env: {...process.env, DEWY_LSP_CHECK_DELAY_MS: '3000'},
            stdio: ['pipe', 'pipe', 'pipe'],
        });
        this.messages = [];
        this.buffer = Buffer.alloc(0);
        this.stderr = '';
        this.error = null;
        this.ended = false;
        this.process.on('error', error => { this.error = error; });
        this.process.on('exit', () => { this.ended = true; });
        this.process.stdin.on('error', error => { this.error = error; });
        this.process.stderr.on('data', bytes => { this.stderr += bytes; });
        this.process.stdout.on('data', bytes => {
            this.buffer = Buffer.concat([this.buffer, bytes]);
            for (;;) {
                const end = this.buffer.indexOf('\r\n\r\n');
                if (end < 0) break;
                const length = Number(/Content-Length:\s*(\d+)/i.exec(this.buffer.subarray(0, end))[1]);
                if (this.buffer.length < end + 4 + length) break;
                this.messages.push(JSON.parse(this.buffer.subarray(end + 4, end + 4 + length)));
                this.buffer = this.buffer.subarray(end + 4 + length);
            }
        });
    }
    send(...messages) { this.process.stdin.write(Buffer.concat(messages.map(frame))); }
    async until(predicate, timeout = 8000) {
        const deadline = performance.now() + timeout;
        while (!predicate()) {
            if (this.error) throw this.error;
            assert(!this.ended, `server exited: ${this.stderr}`);
            assert(performance.now() < deadline, `protocol timeout: ${JSON.stringify(this.messages)}\n${this.stderr}`);
            await pause(10);
        }
    }
    async reply(id, timeout) {
        await this.until(() => this.messages.some(m => m.id === id), timeout);
        return this.messages.find(m => m.id === id);
    }
    async started(count) {
        await this.until(() => this.stderr.split('test checker started').length - 1 >= count);
    }
    async initialize() {
        this.send({id: 'init', method: 'initialize', params: {
            capabilities: {}, rootUri: pathToFileURL(directory).href,
        }});
        assert((await this.reply('init')).result.capabilities);
        this.send({method: 'initialized', params: {}});
    }
    diagnostics() {
        return this.messages.filter(m => m.method === 'textDocument/publishDiagnostics' && m.params.uri === uri);
    }
    async close() {
        if (this.ended) return;
        this.send({id: 'shutdown', method: 'shutdown', params: null});
        try {
            assert.equal((await this.reply('shutdown', 1500)).result, null);
            this.send({method: 'exit', params: null});
            const deadline = performance.now() + 1500;
            while (!this.ended && performance.now() < deadline) await pause(10);
            assert(this.ended, 'server did not exit after shutdown');
        } finally {
            if (!this.ended) this.process.kill();
        }
    }
}

async function scenario(run) {
    const client = new Client();
    try {
        await client.initialize();
        await run(client);
    } finally { await client.close(); }
}

(async () => {
    // Both a handler that refreshes a dirty document and one that checks speculative completion
    // text must retain the request ID throughout checking and restore the document afterwards.
    for (const method of ['textDocument/hover', 'textDocument/completion', 'textDocument/prepareRename']) {
        await scenario(async c => {
            const id = 'cancel "escaped" Ω id';
            const params = document;
            c.send(opened(), {id, method, params});
            await c.started(1);
            c.send({method: '$/cancelRequest', params: {id}});
            const cancelled = await c.reply(id, 1500);
            assert.equal(cancelled.error?.code, -32800, JSON.stringify(cancelled));
            assert.equal(c.diagnostics().length, 0, 'cancelled check published diagnostics');
            c.send({id: 'recovered', method: 'textDocument/hover', params: document});
            const recovered = await c.reply('recovered');
            assert.match(JSON.stringify(recovered.result), /answer/);
            assert(!JSON.stringify(recovered).includes('__sloppy_complete__'));
            assert(c.diagnostics().every(m => m.params.diagnostics.length === 0));
        });
    }
    // A changed document interrupts background checking. Queued JSON must not overwrite the
    // active handler's parser nodes; method-like strings inside document text are ordinary data.
    await scenario(async c => {
        c.send(opened());
        await c.started(1);
        c.send(changed(2), {id: 1234, method: 'textDocument/hover', params: document});
        await c.started(2);
        c.send({method: 'ignored/notification', params: {
            text: `"$/cancelRequest" "textDocument/didChange" ${uri}`, id: 1234,
        }}, {method: '$/cancelRequest', params: {id: '1234'}});
        assert.match(JSON.stringify((await c.reply(1234)).result), /answer/);
        assert.deepEqual(c.diagnostics().map(m => m.params.version), [2]);
    });
    // A request already checking the old version is answered ContentModified, and closing
    // its document also stops it. Neither path may publish the abandoned version's findings.
    for (const method of ['textDocument/didChange', 'textDocument/didClose']) {
        await scenario(async c => {
            c.send(opened(), {id: 'old', method: 'textDocument/hover', params: document});
            await c.started(1);
            if (method === 'textDocument/didChange') {
                c.send(changed(2), {id: 'new', method: 'textDocument/hover', params: document});
            } else c.send({method, params: document});
            assert.equal((await c.reply('old', 1500)).error?.code, -32801);
            if (method === 'textDocument/didChange') {
                assert.match(JSON.stringify((await c.reply('new')).result), /answer/);
                assert.deepEqual(c.diagnostics().map(m => m.params.version), [2]);
            } else assert(c.diagnostics().every(m => m.params.diagnostics.length === 0));
        });
    }
    await scenario(async c => {
        c.send(opened());
        await c.started(1);
        c.process.stdin.end();
        await c.until(() => c.ended, 1500);
        assert.equal(c.process.exitCode, 0);
    });
    // Receiving only part of a frame must not hold a finished checker hostage. Finish that
    // same frame afterwards and verify that framing and subsequent responses still work.
    for (const part of ['header', 'body']) {
        await scenario(async c => {
            c.send(opened(), {id: 99, method: 'textDocument/hover', params: document});
            await c.started(1);
            const message = frame({method: 'ignored/notification', params: {text: 'fragmented'}});
            const cut = part === 'header' ? 5 : message.length - 5;
            c.process.stdin.write(message.subarray(0, cut));
            assert.match(JSON.stringify((await c.reply(99, 5000)).result), /answer/);
            c.process.stdin.write(message.subarray(cut));
        });
    }
    console.log('running cancellation, changed text, parser state and fragmented frames passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
