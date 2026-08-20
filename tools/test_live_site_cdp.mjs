/**
 * ALLTHINGS140 Radio — Headless Chrome CDP Live Site Inspector
 * Connects directly to Chrome DevTools Protocol without third-party frameworks.
 * Captures console errors, network requests, video playback metrics, DOM state, and responsive behavior.
 */

import { spawn } from 'child_process';
import http from 'http';

const CHROME_PORT = 9333;
const TARGET_URL = process.argv[2] || 'https://allthings140radio.online';
const VIEWPORT_WIDTH = parseInt(process.argv[3] || '1920', 10);
const VIEWPORT_HEIGHT = parseInt(process.argv[4] || '1080', 10);

console.log(`=== Inspecting ${TARGET_URL} in Headless Chrome (${VIEWPORT_WIDTH}x${VIEWPORT_HEIGHT}) ===`);

// 1. Launch Chrome in headless mode with remote debugging
const chromeProc = spawn('google-chrome', [
  '--headless=new',
  `--remote-debugging-port=${CHROME_PORT}`,
  '--no-sandbox',
  '--disable-gpu',
  '--disable-dev-shm-usage',
  '--autoplay-policy=no-user-gesture-required',
  '--mute-audio',
  `--window-size=${VIEWPORT_WIDTH},${VIEWPORT_HEIGHT}`,
  'about:blank'
], { stdio: 'ignore' });

function cleanup() {
  try { chromeProc.kill(); } catch {}
}
process.on('exit', cleanup);
process.on('SIGINT', () => { cleanup(); process.exit(1); });

// Wait for Chrome CDP endpoint to be ready
async function waitForChrome(retries = 30) {
  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${CHROME_PORT}/json/version`);
      if (res.ok) return await res.json();
    } catch {}
    await new Promise(r => setTimeout(r, 200));
  }
  throw new Error('Could not connect to Chrome CDP');
}

async function run() {
  await waitForChrome();
  
  // Create new target tab
  const newTabRes = await fetch(`http://127.0.0.1:${CHROME_PORT}/json/new?${encodeURIComponent(TARGET_URL)}`, { method: 'PUT' });
  const tabData = await newTabRes.json();
  const wsUrl = tabData.webSocketDebuggerUrl;

  const ws = new WebSocket(wsUrl);
  let msgId = 1;
  const pending = new Map();
  const consoleLogs = [];
  const networkRequests = [];
  const networkFailed = [];

  function send(method, params = {}) {
    const id = msgId++;
    return new Promise((resolve, reject) => {
      pending.set(id, { resolve, reject });
      ws.send(JSON.stringify({ id, method, params }));
    });
  }

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) reject(msg.error);
      else resolve(msg.result);
      return;
    }

    if (msg.method === 'Runtime.consoleAPICalled') {
      const args = (msg.params.args || []).map(a => a.value !== undefined ? a.value : (a.description || a.type)).join(' ');
      consoleLogs.push(`[Console ${msg.params.type}] ${args}`);
    } else if (msg.method === 'Runtime.exceptionThrown') {
      const desc = msg.params.exceptionDetails.exception?.description || msg.params.exceptionDetails.text;
      consoleLogs.push(`[JS Exception] ${desc} at line ${msg.params.exceptionDetails.lineNumber}:${msg.params.exceptionDetails.columnNumber}`);
    } else if (msg.method === 'Network.responseReceived') {
      const r = msg.params.response;
      networkRequests.push({ url: r.url, status: r.status, mime: r.mimeType, headers: r.headers });
      if (r.status >= 400) {
        networkFailed.push({ url: r.url, status: r.status, statusText: r.statusText });
      }
    } else if (msg.method === 'Network.loadingFailed') {
      networkFailed.push({ url: msg.params.url || 'unknown', errorText: msg.params.errorText, type: msg.params.type });
    }
  };

  await new Promise(r => ws.onopen = r);

  // Enable CDP domains
  await send('Page.enable');
  await send('Runtime.enable');
  await send('Network.enable');
  await send('Emulation.setDeviceMetricsOverride', {
    width: VIEWPORT_WIDTH,
    height: VIEWPORT_HEIGHT,
    deviceScaleFactor: 1,
    mobile: VIEWPORT_WIDTH <= 680
  });

  // Navigate to target
  await send('Page.navigate', { url: TARGET_URL });

  // Wait 4 seconds for media, scripts, and status polling
  await new Promise(r => setTimeout(r, 4500));

  // Evaluate DOM and Video status
  const evalResult = await send('Runtime.evaluate', {
    expression: `(() => {
      const bgVideo = document.querySelector('#backgroundVideo');
      const visVideo = document.querySelector('#visualVideo');
      const activeVideo = bgVideo || visVideo;
      
      const videoInfo = activeVideo ? {
        id: activeVideo.id,
        src: activeVideo.src,
        currentSrc: activeVideo.currentSrc,
        paused: activeVideo.paused,
        currentTime: activeVideo.currentTime,
        duration: activeVideo.duration,
        readyState: activeVideo.readyState,
        networkState: activeVideo.networkState,
        videoWidth: activeVideo.videoWidth,
        videoHeight: activeVideo.videoHeight,
        muted: activeVideo.muted,
        autoplay: activeVideo.autoplay,
        loop: activeVideo.loop,
        playsInline: activeVideo.playsInline,
        error: activeVideo.error ? { code: activeVideo.error.code, message: activeVideo.error.message } : null,
        dataset: Object.assign({}, activeVideo.dataset),
        sources: Array.from(activeVideo.querySelectorAll('source')).map(s => ({
          src: s.src,
          type: s.type,
          media: s.media
        })),
        computedStyle: {
          display: getComputedStyle(activeVideo).display,
          visibility: getComputedStyle(activeVideo).visibility,
          opacity: getComputedStyle(activeVideo).opacity,
          zIndex: getComputedStyle(activeVideo).zIndex,
          position: getComputedStyle(activeVideo).position,
          width: getComputedStyle(activeVideo).width,
          height: getComputedStyle(activeVideo).height
        }
      } : null;

      const bgMedia = document.querySelector('.bg-media');
      const bgMediaStyle = bgMedia ? {
        display: getComputedStyle(bgMedia).display,
        visibility: getComputedStyle(bgMedia).visibility,
        opacity: getComputedStyle(bgMedia).opacity,
        zIndex: getComputedStyle(bgMedia).zIndex,
        position: getComputedStyle(bgMedia).position
      } : null;

      const nowPlaying = {
        title: document.querySelector('#trackTitle, #nowPlayingTitle')?.textContent || '',
        artist: document.querySelector('#trackArtist, #nowPlayingArtist')?.textContent || '',
        status: document.querySelector('#headerStatus, #nowPlayingLabel')?.textContent || ''
      };

      const motionToggle = document.querySelector('#motionToggle');
      const motionToggleInfo = motionToggle ? {
        text: motionToggle.textContent,
        ariaPressed: motionToggle.getAttribute('aria-pressed')
      } : null;

      return {
        title: document.title,
        bodyClasses: document.body.className,
        video: videoInfo,
        bgMediaStyle,
        nowPlaying,
        motionToggle: motionToggleInfo
      };
    })()`,
    returnByValue: true
  });

  console.log('\n--- DOM & MEDIA STATUS ---');
  console.log(JSON.stringify(evalResult.result.value, null, 2));

  console.log('\n--- BROWSER CONSOLE LOGS ---');
  if (consoleLogs.length === 0) {
    console.log('(No console errors or messages)');
  } else {
    consoleLogs.forEach(l => console.log(l));
  }

  console.log('\n--- NETWORK REQUESTS SUMMARY ---');
  console.log(`Total Requests: ${networkRequests.length}`);
  const mediaReqs = networkRequests.filter(r => r.mime?.includes('video') || r.url.endsWith('.mp4') || r.url.endsWith('.m3u8') || r.url.endsWith('.ts'));
  console.log(`Media Requests (${mediaReqs.length}):`);
  mediaReqs.forEach(r => console.log(`  [${r.status}] ${r.mime} — ${r.url}`));

  console.log('\n--- FAILED NETWORK REQUESTS ---');
  if (networkFailed.length === 0) {
    console.log('(Zero failed network requests)');
  } else {
    networkFailed.forEach(f => console.log(`  [FAILED] ${f.status || ''} ${f.errorText || ''} — ${f.url}`));
  }

  ws.close();
  cleanup();
  process.exit(0);
}

run().catch(err => {
  console.error('Inspector Error:', err);
  cleanup();
  process.exit(1);
});
