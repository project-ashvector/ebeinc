import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const ROOT = path.resolve(import.meta.dirname, '..');
const read = (file) => fs.readFileSync(path.join(ROOT, file), 'utf8');
const hash = (file) => crypto.createHash('sha256').update(read(file)).digest('hex');
let passed = 0;
function check(condition, message) {
  if (!condition) throw new Error(`FAIL: ${message}`);
  passed += 1;
  console.log(`✓ ${message}`);
}

const shell = read('radio/persistent-shell.html');
const router = read('radio/persistent-shell.js');
const routeBoot = read('radio/persistent-route.js');
const adapter = read('radio/persistent-audio-adapter.js');
const sw = read('radio/sw.js');

check((shell.match(/<audio\b/g) || []).length === 1, 'persistent shell owns exactly one audio element');
check(shell.includes('id="routeFrame"'), 'route content is isolated from the persistent shell');
check(router.includes('history.pushState') && router.includes('popstate'), 'router owns forward navigation and Back/Forward');
check(router.includes('contentWindow.location.replace'), 'route swaps do not pollute joint iframe history');
check(router.includes('releaseRoute()') && router.includes('PageTransitionEvent("pagehide")'), 'route teardown invokes page lifecycle cleanup');
check(router.includes('clients.get(currentClient)?.destroy()'), 'route audio-event clients are released');
check(router.includes('audioElements: document.querySelectorAll("audio").length'), 'single-player runtime invariant is inspectable');
check(router.includes('savedVolumeRaw !== null'), 'first-time listeners are not initialized at zero volume');
check(routeBoot.includes('document.querySelectorAll("audio").forEach((node) => node.remove())'), 'embedded route audio nodes are removed');
check(routeBoot.includes('setTimeout(() => window.top.AT140Navigate?.(url.href), 0)'), 'every embedded route defers eligible links safely to the shell router');
check(routeBoot.includes('window.addEventListener("unload"'), 'route frames opt out of BFCache retention');
check(adapter.includes('window.top.AT140Radio.client(window)'), 'legacy Room controls delegate to shell audio authority');

for (const file of ['radio/index.html', 'radio/roadmap/index.html', 'radio/visuals/index.html', 'radio/visuals/legacy.html', 'radio/room/index.html']) {
  check(read(file).includes('persistent-route.js'), `${file} enters the persistent shell on direct load`);
}
check(read('radio/app.js').includes('window.top.AT140Radio.client(window)'), 'Home controls consume shell audio authority');
check(read('radio/roadmap/index.html').includes('window.top.AT140Radio.client(window)'), 'Roadmap controls consume shell audio authority');
check(read('radio/visuals/legacy.html').includes('window.top.AT140Radio.client(window)'), 'legacy Visuals controls consume shell audio authority');
check(hash('radio/room/stage.js') === hash('visuals-green/stage.js'), 'Room compositor engine remains byte-identical to frozen Green engine');
check(sw.includes('allthings140-radio-v68'), 'service-worker cache namespace is advanced');
check(sw.includes('mp4|webm|mp3|m3u8|ts'), 'service worker continues bypassing live and visual media');
check(read('radio/_headers').includes("frame-ancestors 'self'"), 'Room permits only same-origin persistent-shell framing');
check(read('radio/_headers').includes('/persistent-shell.js\n  Cache-Control: no-store'), 'router assets are not served stale');
check(read('radio/sw.js') === read('radio/sw-v47.js'), 'both service-worker entry files remain synchronized');

console.log(`Phase A persistent-radio contract: ${passed} checks passed.`);
