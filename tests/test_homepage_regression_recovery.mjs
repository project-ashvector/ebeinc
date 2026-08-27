import fs from 'node:fs';
import assert from 'node:assert/strict';

const read = path => fs.readFileSync(path, 'utf8');
const home = read('radio/index.html');
const styles = read('radio/styles.css');
const sw = read('radio/sw.js');

assert.match(home, /styles\.css\?v=2\.1\.3/, 'homepage requests the repaired stylesheet revision');
assert.match(home, /id="backgroundVideo"[\s\S]*autoplay muted loop playsinline/, 'homepage retains safe autoplay video attributes');
assert.match(home, /main-vis-home-hq-v2\.mp4\?v=2\.0\.0/, 'homepage references the high-quality web derivative of the user-selected master');
assert.match(home, /main-vis-home-v1-poster\.webp\?v=1\.0\.0/, 'homepage poster matches the user-selected video');
assert.match(styles, /\.home-route-grid\{display:grid/, 'route CTAs have their intended grid styling');
assert.match(styles, /\.home-route-grid a\{[^}]*display:flex/, 'route CTAs cannot fall back to raw inline links');
assert.match(sw, /allthings140-radio-v68/, 'service worker activates a new cache generation');
assert.match(home, /app\.js\?v=2\.0\.3/, 'homepage requests the repaired motion-preference revision');
assert.doesNotMatch(styles, /translateZ\(0\)/, 'background video avoids fragile forced GPU compositing');
assert.match(read('radio/app.js'), /localStorage\.removeItem\("allthings140-reduced-motion"\)/, 'legacy stuck motion-off preference is migrated');
assert.match(sw, /url\.pathname\.endsWith\("\/styles\.css"\)/, 'stylesheet is network-first after upgrades');
assert.match(sw, /\.\(\?:mp4\|webm\|mp3\|m3u8\|ts\)/, 'video remains outside CacheStorage');
assert.equal(sw, read('radio/sw-v47.js'), 'service-worker entry points remain identical');

console.log('homepage regression recovery contract: PASS');
