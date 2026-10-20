// Exercise the actual web input handlers without a browser/GPU or a compiler build.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
class Events {
  constructor() { this.handlers = new Map(); this.style = {}; }
  addEventListener(name, handler) {
    if (!this.handlers.has(name)) this.handlers.set(name, []);
    this.handlers.get(name).push(handler);
  }
  send(name, event = {}) { for (const h of this.handlers.get(name) || []) h(event); }
  setAttribute() {}
  focus() {}
}
const canvas = new Events();
canvas.getBoundingClientRect = () => ({left: 0, top: 0, width: 1280, height: 800});
canvas.getContext = () => ({});
const doc = new Events();
doc.body = new Events();
doc.body.appendChild = () => {};
doc.createElement = () => new Events();
doc.getElementById = (id) => id === 'sloppy-canvas' ? canvas : new Events();
doc.pointerLockElement = null;
const win = new Events();
Object.assign(win, {innerWidth: 1280, innerHeight: 800, devicePixelRatio: 1});
let x = 0, y = 0, dx = 0, dy = 0;
const events = [];
const ex = {__mouse(kind, a, b, button) {
  events.push([kind, a, b, button]);
  if (kind === 0) { dx += a-x; dy += b-y; x = a; y = b; }
  if (kind === 4) { dx += a; dy += b; }
  if (kind === 5) { dx = 0; dy = 0; }
}};
const sloppy = {extra: []};
const source = fs.readFileSync(path.resolve(__dirname, '../lib/web/gfx.js'), 'utf8');
vm.runInNewContext(source, {sloppy, document: doc, window: win, TextDecoder, TextEncoder});
const memory = {buffer: new ArrayBuffer(32)};
sloppy.extra[0].imports(() => memory, () => ex).__web_canvas_open(0, 0, 1280, 720);
const move = (a, b, mx = 0, my = 0) => canvas.send('mousemove', {clientX: a, clientY: b, movementX: mx, movementY: my});
move(640, 400);
assert.deepEqual([dx, dy], [640, 400]);
// Capturing: the observed Chromium sequence sends a warp BEFORE its lock event.
doc.pointerLockElement = canvas;
move(640, 400, -640, -400);
assert.deepEqual([dx, dy], [0, 0]);
doc.send('pointerlockchange');
move(640, 400, 4, -3);
assert.deepEqual([dx, dy], [4, -3]);
// Repeated lock notifications must not discard real motion.
doc.send('pointerlockchange');
assert.deepEqual([dx, dy], [4, -3]);
// Unlock with the move first also updates the absolute position without a delta.
doc.pointerLockElement = null;
move(700, 420, 60, 20);
assert.deepEqual([x, y, dx, dy], [700, 420, 0, 0]);
doc.send('pointerlockchange');
move(710, 425);
assert.deepEqual([dx, dy], [10, 5]);
// If the lock event arrives first, retain the first real relative motion.
doc.pointerLockElement = canvas;
doc.send('pointerlockchange');
move(710, 425, 2, 7);
assert.deepEqual([dx, dy], [2, 7]);
canvas.send('mousedown', {clientX: 710, clientY: 425, button: 0});
win.send('mouseup', {button: 0});
assert.deepEqual(events.slice(-2).map(e => [e[0], e[3]]), [[1, 0], [2, 0]]);
console.log('pointer lock transitions passed');
