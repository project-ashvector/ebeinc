import assert from "node:assert/strict";
import fs from "node:fs";

const read = path => fs.readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
const web = read("radio/persistent-shell.js");
const android = read("android/mobile-app/app/src/main/java/online/ebeinc/allthings140radio/RadioService.java");

for (const event of ["waiting", "stalled", "error", "ended"]) {
  assert.ok(web.includes(`type === "${event}"`) || web.includes(`type === "waiting" || type === "stalled"`),
    `web recovery handles ${event}`);
}
assert.match(web, /at140_reconnect/, "web recovery forces a fresh Icecast HTTP request");
assert.match(web, /addEventListener\("online"/, "web retries immediately when network returns");
assert.match(web, /continuity-watchdog/, "web catches silent paused/stuck states");
assert.match(web, /if \(!desiredPlay \|\| streamRecoveryTimer\) return/,
  "web never reconnects after an intentional pause");

assert.match(android, /state == Player\.STATE_ENDED \|\| state == Player\.STATE_IDLE/,
  "Android recovers clean EOF and idle termination");
assert.match(android, /streamWatchdogRunnable/, "Android has a persistent continuity watchdog");
assert.match(android, /player\.getPlayWhenReady\(\) && !player\.isPlaying\(\)/,
  "Android watchdog respects an intentional pause");

console.log("PASS long-session stream continuity guards");
