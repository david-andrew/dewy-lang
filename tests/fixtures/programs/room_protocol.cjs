// Exercise the real server with browser-compatible WebSocket messages.
const assert = require('node:assert/strict');
const timer = setTimeout(() => {console.error('room protocol timed out'); process.exit(1);}, 8000);
async function connect() {
    const ws = new WebSocket(`ws://127.0.0.1:${process.argv[2]}`);
    const messages = [];
    let wake;
    ws.onmessage = e => {messages.push(e.data); if (wake) {wake(); wake = undefined;}};
    await new Promise((resolve, reject) => {ws.onopen = resolve; ws.onerror = reject;});
    return {
        send: text => ws.send(text),
        async next() {while (!messages.length) await new Promise(resolve => {wake = resolve;}); return messages.shift();},
        async expect(text) {assert.equal(await this.next(), text);},
        async close() {await new Promise(resolve => {ws.onclose = resolve; ws.close();});},
    };
}
(async () => {
    const guest = await connect(), host = await connect(), other = await connect();
    // A saved room survives the server starting; unrelated games can reuse its code.
    host.send('host game SAVED wrong-key'); await host.expect('taken');
    host.send('host game SAVED saved-key'); await host.expect('hosting SAVED');
    other.send('host another SAVED other-key'); await other.expect('hosting SAVED');
    guest.send('join game ABCD'); await guest.expect('wait new');
    host.send('host game ABCD test-key'); await host.expect('hosting ABCD');
    const first = await host.next(); assert.match(first, /^guest \d+$/);
    const id = first.split(' ')[1];
    await guest.expect('asking');
    host.send(`invite ${id} offer-code`); await guest.expect('invite offer-code');
    guest.send('reply reply-code'); await host.expect(`reply ${id} reply-code`);
    host.send(`done ${id}`);
    host.send('busy'); host.send('ping'); await host.expect('pong');
    guest.send('join game ABCD'); await guest.expect('wait busy');
    host.send('open'); await host.expect(`guest ${id}`); await guest.expect('asking');
    await host.close(); await guest.expect('wait host');
    const again = await connect();
    again.send('host game ABCD test-key'); await again.expect('hosting ABCD');
    await again.expect(`guest ${id}`); await guest.expect('asking');
    const replacement = await connect();
    replacement.send('host game ABCD test-key'); await replacement.expect('hosting ABCD');
    await again.expect('replaced'); await replacement.expect(`guest ${id}`); await guest.expect('asking');
    await guest.close(); await replacement.expect(`gone ${id}`);
    await again.close(); await replacement.close(); await other.close();
    clearTimeout(timer); console.log('complete');
})().catch(error => {console.error(error); process.exit(1);});
