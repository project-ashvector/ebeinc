import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { writeFileSync } from 'node:fs';

const url = process.env.AT140_GREEN_RUNTIME_URL;
assert(url, 'AT140_GREEN_RUNTIME_URL is required');
const port = 9444;
const profile = `/tmp/at140-green-runtime-test-${process.pid}`;
const chrome = spawn('google-chrome', [
  '--headless=new', '--no-sandbox', '--disable-gpu',
  '--autoplay-policy=no-user-gesture-required',
  `--remote-debugging-port=${port}`,
  `--user-data-dir=${profile}`,
  '--window-size=1440,900', url,
], { stdio: ['ignore', 'ignore', 'pipe'] });
let chromeError = '';
chrome.stderr.on('data', chunk => { chromeError += String(chunk); });

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function targets() {
  for (let attempt = 0; attempt < 80; attempt++) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/list`);
      if (response.ok) return response.json();
    } catch {}
    await sleep(250);
  }
  throw new Error(`Chrome CDP did not start: ${chromeError.slice(-1000)}`);
}

let nextId = 1;
const pending = new Map();
function rpc(ws, method, params = {}) {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
}

try {
  const page = (await targets()).find(target => target.type === 'page' && target.url.startsWith('http'));
  assert(page, 'runtime page target is present');
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  ws.onmessage = event => {
    const message = JSON.parse(event.data);
    if (!message.id || !pending.has(message.id)) return;
    const promise = pending.get(message.id);
    pending.delete(message.id);
    message.error ? promise.reject(new Error(message.error.message)) : promise.resolve(message.result);
  };
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
  await rpc(ws, 'Runtime.enable');
  await rpc(ws, 'Page.enable');
  await sleep(12000);

  async function evaluate(expression) {
    const result = await rpc(ws, 'Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
    return result.result.value;
  }

  const initial = await evaluate(`({
    transport: !!window.AT140_VISUAL_TRANSPORT,
    state: window.AT140_VISUAL_TRANSPORT?.state(),
    stageReady: document.querySelector('#stageVideo')?.readyState || 0,
    activeId: document.querySelector('#screens video.active')?.dataset.id || '',
    activeReady: document.querySelector('#screens video.active')?.readyState || 0,
    videoCount: document.querySelectorAll('#screens video').length,
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
  })`);
  assert(initial.transport, 'transport is exposed');
  assert.equal(initial.state.playlistCount, 95, 'authoritative playlist contains 95 visuals');
  assert.equal(initial.videoCount, 2, 'renderer retains exactly two bounded video buffers');
  assert(initial.stageReady >= 2, `Stage is decodable (readyState ${initial.stageReady})`);
  assert(initial.activeReady >= 2, `initial Visual is decodable (readyState ${initial.activeReady})`);

  const transitions = [];
  let previous = initial.activeId;
  for (let index = 0; index < 20; index++) {
    await evaluate('window.AT140_VISUAL_TRANSPORT.next()');
    let current = previous;
    for (let attempt = 0; attempt < 100 && current === previous; attempt++) {
      await sleep(150);
      current = await evaluate("document.querySelector('#screens video.active')?.dataset.id || ''");
    }
    assert(current && current !== previous, `transition ${index + 1} changed the active Visual`);
    const state = await evaluate(`({
      id: document.querySelector('#screens video.active')?.dataset.id || '',
      ready: document.querySelector('#screens video.active')?.readyState || 0,
      videoCount: document.querySelectorAll('#screens video').length,
      heap: performance.memory?.usedJSHeapSize || null,
      at: Date.now(),
    })`);
    assert(state.ready >= 2, `transition ${index + 1} decoded a frame`);
    assert.equal(state.videoCount, 2, `transition ${index + 1} retained two buffers`);
    transitions.push(state);
    previous = current;
  }
  assert.equal(new Set(transitions.map(item => item.id)).size, 20, '20 transitions produced 20 distinct consecutive Visuals');

  const shot = await rpc(ws, 'Page.captureScreenshot', { format: 'png', fromSurface: true });
  writeFileSync('/home/ebmarah/Documents/at140-visuals-green-runtime-after-20.png', Buffer.from(shot.data, 'base64'));
  console.log(JSON.stringify({ initial, transitions, result: 'PASS' }, null, 2));
  ws.close();
} finally {
  chrome.kill('SIGTERM');
}
