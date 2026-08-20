const PUBLIC_API_ORIGIN = "https://status.ebeinc.online";
const OBS_STREAM_ORIGIN = "https://stream.ebeinc.online/live.mp3";
const PUBLIC_GET_PATH = /^\/api\/public\/(?:status|schedule|support(?:\/status)?|takeover-invite\/[A-Za-z0-9_-]+|takeover-logo\/[a-f0-9]{32}\.(?:png|jpg|webp)|archive(?:\/[^/]+\/(?:audio|waveform))?|alerts)$/;
const PUBLIC_POST_PATH = /^\/api\/public\/(?:support\/(?:checkout|webhook)|requests|submissions|newsletter|takeover-interest|takeover-invite\/[A-Za-z0-9_-]+)$/;
const MAILCHIMP_SERVER = "us7";
const MAILCHIMP_AUDIENCE = "b9ed48d509";
const WELCOME_TAG = "Welcome Sent";

function mailchimpHeaders(env, json = false) {
  const headers = { "Authorization": `Basic ${btoa(`allthings140:${env.MAILCHIMP_API_KEY}`)}` };
  if (json) headers["Content-Type"] = "application/json";
  return headers;
}

function welcomeEmailHtml() {
  return `<!doctype html><html><body style="margin:0;background:#09030f;color:#f7f1ff;font-family:Arial,sans-serif"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#09030f"><tr><td align="center" style="padding:32px 16px"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:620px;background:#14071f;border:1px solid #7d25c7"><tr><td style="padding:40px"><p style="margin:0 0 12px;color:#d889ff;font-size:13px;font-weight:bold;letter-spacing:2px">ALLTHINGS140RADIO</p><h1 style="margin:0 0 20px;color:#fff;font-size:30px">Thank you for joining the newsletter!</h1><p style="margin:0 0 18px;color:#d8cde0;font-size:17px;line-height:1.6">You&rsquo;re officially on the list. We&rsquo;ll keep you updated about upcoming artist takeovers, special broadcasts, station announcements, and new music.</p><p style="margin:28px 0"><a href="https://allthings140radio.online/#schedule" style="display:inline-block;background:#8b2be2;color:#fff;text-decoration:none;font-weight:bold;padding:14px 22px">VIEW THE TAKEOVER SCHEDULE</a></p><p style="margin:24px 0 0;color:#bbaac5;font-size:15px;line-height:1.5">Keep it loud,<br><strong style="color:#fff">AllThings140Radio</strong></p><hr style="border:0;border-top:1px solid #382246;margin:32px 0 20px"><p style="margin:0;color:#8f8198;font-size:12px;line-height:1.5">You received this because you confirmed your AllThings140Radio newsletter subscription. To leave the list, use the unsubscribe link in any newsletter or reply with &ldquo;unsubscribe.&rdquo;</p></td></tr></table></td></tr></table></body></html>`;
}

async function sendConfirmedWelcome(email, env, subscriberHash) {
  if (!env.MAILCHIMP_API_KEY || !env.RESEND_API_KEY) return { ok: false, reason: "not_configured" };
  if (!/^[a-f0-9]{32}$/i.test(String(subscriberHash || ""))) return { ok: false, reason: "member_id_missing" };
  const base = `https://${MAILCHIMP_SERVER}.api.mailchimp.com/3.0/lists/${MAILCHIMP_AUDIENCE}/members/${subscriberHash}`;
  const memberResponse = await fetch(base, { headers: mailchimpHeaders(env) });
  if (!memberResponse.ok) return { ok: false, reason: "member_not_found" };
  const member = await memberResponse.json();
  if (member.status !== "subscribed") return { ok: false, reason: "not_subscribed" };
  if ((member.tags || []).some((tag) => tag.name === WELCOME_TAG)) return { ok: true, duplicate: true };

  const sendResponse = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { "Authorization": `Bearer ${env.RESEND_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      from: "AllThings140Radio <newsletter@allthings140radio.online>",
      to: [email],
      subject: "Thank you for joining AllThings140Radio",
      html: welcomeEmailHtml(),
      text: "Thank you for joining the AllThings140Radio newsletter! You’re officially on the list. We’ll keep you updated about artist takeovers, special broadcasts, station announcements, and new music. View the schedule: https://allthings140radio.online/#schedule",
    }),
  });
  if (!sendResponse.ok) {
    let detail = "unknown";
    try { const body = await sendResponse.json(); detail = String(body.message || body.name || "unknown").slice(0, 160); } catch {}
    console.error("resend_welcome_failed", { status: sendResponse.status, detail });
    return { ok: false, reason: "send_failed", status: sendResponse.status, detail };
  }
  await fetch(`${base}/tags`, {
    method: "POST",
    headers: mailchimpHeaders(env, true),
    body: JSON.stringify({ tags: [{ name: WELCOME_TAG, status: "active" }] }),
  });
  return { ok: true };
}

async function handleMailchimpWebhook(request, env) {
  let form;
  try { form = await request.formData(); } catch { return Response.json({ error: "Invalid webhook" }, { status: 400 }); }
  if (form.get("type") !== "subscribe" || form.get("data[list_id]") !== MAILCHIMP_AUDIENCE) return new Response(null, { status: 204 });
  const email = String(form.get("data[email]") || "").trim().toLowerCase();
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return Response.json({ error: "Invalid webhook" }, { status: 400 });
  const result = await sendConfirmedWelcome(email, env, String(form.get("data[id]") || ""));
  return result.ok ? new Response(null, { status: 204 }) : Response.json({ error: result.reason }, { status: 502 });
}

async function mailchimpSignup(request, env) {
  if (!env.MAILCHIMP_API_KEY) return null;
  let data;
  try { data = await request.json(); } catch { return Response.json({ error: "Invalid request" }, { status: 400 }); }
  const email = String(data.email || "").trim().toLowerCase();
  if (!data.consent || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    return Response.json({ error: "A valid email and reminder consent are required." }, { status: 400 });
  }
  const response = await fetch(`https://${MAILCHIMP_SERVER}.api.mailchimp.com/3.0/lists/${MAILCHIMP_AUDIENCE}/members`, {
    method: "POST",
    headers: { "Authorization": `Basic ${btoa(`allthings140:${env.MAILCHIMP_API_KEY}`)}`, "Content-Type": "application/json" },
    body: JSON.stringify({ email_address: email, status: "pending", tags: ["Takeover Reminders"] }),
  });
  const result = await response.json();
  if (!response.ok && result.title !== "Member Exists") {
    console.error("mailchimp_signup_failed", { status: response.status, title: result.title });
    return Response.json({ error: "Reminder signup is temporarily unavailable." }, { status: 502 });
  }
  return Response.json({ ok: true, message: result.title === "Member Exists" ? "You’re already on the reminder list." : "Check your email to confirm takeover reminders." }, { status: result.title === "Member Exists" ? 200 : 201 });
}

function takeoverAlertHtml(takeover) {
  const esc = (value) => String(value || "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
  const when = new Date(Number(takeover.starts_at) * 1000).toLocaleString("en-US", { timeZone: takeover.timezone || "America/Los_Angeles", dateStyle: "full", timeStyle: "short" });
  return `<!doctype html><html><body style="margin:0;background:#09030f;color:#f7f1ff;font-family:Arial,sans-serif"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#09030f"><tr><td align="center" style="padding:28px 12px"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:650px;background:#14071f;border:1px solid #7d25c7"><tr><td style="padding:36px"><p style="color:#d889ff;font-size:13px;font-weight:bold;letter-spacing:2px">ALLTHINGS140RADIO TAKEOVER ALERT</p><h1 style="color:#fff;font-size:32px">${esc(takeover.artist)} is taking over the station.</h1><h2 style="color:#d889ff">${esc(takeover.title || "Live artist takeover")}</h2><p style="color:#fff;font-size:18px"><strong>${esc(when)} ${esc(takeover.timezone || "")}</strong></p><p style="color:#d8cde0;font-size:16px;line-height:1.6">${esc(takeover.details || "Tune in for a live guest takeover on AllThings140Radio.")}</p><p style="margin:26px 0"><a href="https://allthings140radio.online/#schedule" style="display:inline-block;background:#8b2be2;color:#fff;text-decoration:none;font-weight:bold;padding:14px 22px">VIEW SCHEDULE + LISTEN LIVE</a></p><img src="https://allthings140radio.online/assets/takeover-alert-flyer.jpg" width="578" alt="An artist is taking over AllThings140Radio" style="display:block;width:100%;max-width:578px;height:auto;border:0"><p style="color:#8f8198;font-size:12px;line-height:1.5">You received this because you joined AllThings140Radio takeover reminders. You can unsubscribe through Mailchimp or reply with “unsubscribe.”</p></td></tr></table></td></tr></table></body></html>`;
}

async function sendTakeoverAlert(takeover, env) {
  if (!takeover?.id || !env.MAILCHIMP_API_KEY || !env.RESEND_API_KEY) return;
  const tag = `Takeover Alert ${takeover.id}`;
  const response = await fetch(`https://${MAILCHIMP_SERVER}.api.mailchimp.com/3.0/lists/${MAILCHIMP_AUDIENCE}/members?status=subscribed&count=1000&fields=members.id,members.email_address,members.tags`, { headers: mailchimpHeaders(env) });
  if (!response.ok) return console.error("takeover_alert_members_failed", response.status);
  const members = (await response.json()).members || [];
  const pending = members.filter((member) => !(member.tags || []).some((item) => item.name === tag));
  for (let offset = 0; offset < pending.length; offset += 5) {
    await Promise.all(pending.slice(offset, offset + 5).map(async (member) => {
      const send = await fetch("https://api.resend.com/emails", { method: "POST", headers: { "Authorization": `Bearer ${env.RESEND_API_KEY}`, "Content-Type": "application/json" }, body: JSON.stringify({ from: "AllThings140Radio <newsletter@allthings140radio.online>", to: [member.email_address], subject: `${takeover.artist} is taking over AllThings140Radio`, html: takeoverAlertHtml(takeover), text: `${takeover.artist} is taking over AllThings140Radio. ${takeover.title || "Live artist takeover"}. View the schedule: https://allthings140radio.online/#schedule` }) });
      if (!send.ok) return console.error("takeover_alert_send_failed", member.id, send.status);
      await fetch(`https://${MAILCHIMP_SERVER}.api.mailchimp.com/3.0/lists/${MAILCHIMP_AUDIENCE}/members/${member.id}/tags`, { method: "POST", headers: mailchimpHeaders(env, true), body: JSON.stringify({ tags: [{ name: tag, status: "active" }] }) });
    }));
  }
}

async function sendTakeoverInvite(email, link, env) {
  if (!env.RESEND_API_KEY) throw new Error("Email service unavailable");
  const response = await fetch("https://api.resend.com/emails", { method: "POST", headers: { "Authorization": `Bearer ${env.RESEND_API_KEY}`, "Content-Type": "application/json" }, body: JSON.stringify({ from: "AllThings140Radio <newsletter@allthings140radio.online>", to: [email], subject: "Your private AllThings140Radio takeover form", html: `<!doctype html><html><body style="margin:0;background:#09030f;color:#fff;font-family:Arial,sans-serif"><table role="presentation" width="100%" style="background:#09030f"><tr><td align="center" style="padding:32px 16px"><table role="presentation" width="100%" style="max-width:620px;background:#14071f;border:1px solid #7d25c7"><tr><td style="padding:40px"><p style="color:#d889ff;font-weight:bold;letter-spacing:2px">ALLTHINGS140RADIO</p><h1>Request an artist takeover</h1><p style="color:#d8cde0;font-size:17px;line-height:1.6">Thanks for your interest in taking over the station. Use the private form below to send your artist information, preferred schedule, logo, and social links to the station team for approval.</p><p style="margin:28px 0"><a href="${link}" style="display:inline-block;background:#8b2be2;color:#fff;text-decoration:none;font-weight:bold;padding:14px 22px">OPEN YOUR PRIVATE TAKEOVER FORM</a></p><p style="color:#9f91a8">This private link expires in 14 days and can be submitted once.</p></td></tr></table></td></tr></table></body></html>`, text: `Fill out your private AllThings140Radio takeover request form: ${link}\n\nThe link expires in 14 days and can be submitted once.` }) });
  if (!response.ok) throw new Error(`Resend returned ${response.status}`);
}

async function handleTakeoverAlert(request, env, ctx) {
  const token = request.headers.get("Authorization")?.replace(/^Bearer\s+/i, "").trim() || "";
  const expected = (env.ADMIN_ALERT_KEY || env.TAKEOVER_ALERT_KEY || env.ADMIN_TOKEN || "").trim();
  if (!expected || token !== expected) {
    return Response.json({ error: "Unauthorized" }, { status: 401, headers: { "Cache-Control": "no-store" } });
  }
  let data; try { data = await request.json(); } catch { return Response.json({ error: "Invalid request" }, { status: 400 }); }
  const id = Number(data.id || 0); if (!Number.isInteger(id) || id < 1) return Response.json({ error: "Invalid takeover" }, { status: 400 });
  const schedule = await fetch(`${PUBLIC_API_ORIGIN}/api/public/schedule`, { headers: { "Accept": "application/json" } });
  if (!schedule.ok) return Response.json({ error: "Schedule unavailable" }, { status: 502 });
  const takeover = ((await schedule.json()).takeovers || []).find((item) => Number(item.id) === id);
  if (!takeover) return Response.json({ error: "Approved takeover not found" }, { status: 404 });
  ctx.waitUntil(sendTakeoverAlert(takeover, env));
  return Response.json({ ok: true, message: "Subscriber alert queued." }, { status: 202 });
}

async function obsAudioStream(request, env) {
  const url = new URL(request.url);
  const supplied = url.searchParams.get("key") || "";
  if (!env.OBS_STREAM_TOKEN || supplied !== env.OBS_STREAM_TOKEN) {
    return Response.json({ error: "Not found" }, { status: 404, headers: { "Cache-Control": "no-store" } });
  }
  const upstreamHeaders = new Headers();
  upstreamHeaders.set("Icy-MetaData", "0");
  upstreamHeaders.set("Cache-Control", "no-cache");
  const upstream = await fetch(OBS_STREAM_ORIGIN, { method: request.method, headers: upstreamHeaders, redirect: "follow" });
  const headers = new Headers(upstream.headers);
  headers.set("Cache-Control", "no-store, no-cache, must-revalidate");
  headers.set("Pragma", "no-cache");
  headers.set("Accept-Ranges", "none");
  headers.set("X-Accel-Buffering", "no");
  headers.set("X-AllThings140-OBS", "private-audio-gateway");
  return new Response(request.method === "HEAD" ? null : upstream.body, { status: upstream.status, statusText: upstream.statusText, headers });
}

// ── Visual Routing State ──────────────────────────────────────────────
// KV-backed persistent state for independently controlling Chat tab and
// Visuals tab visual modes. Survives browser refresh, deploy, VM restart.
const DEFAULT_ROUTING = { chat: "legacy", visuals: "legacy" };
const VM2_STATUS_URL = "https://status.ebeinc.online/api/public/status";
const REALTIME_HEALTH_URL = "https://visuals-realtime-staging.allthings140radio.online/health";

async function readRoutingState(env) {
  if (env.VISUALS_ROUTING_KV) {
    const raw = await env.VISUALS_ROUTING_KV.get("routing:v1", { type: "json" });
    if (raw && typeof raw === "object") {
      return {
        chat: raw.chat === "new" ? "new" : "legacy",
        visuals: raw.visuals === "new" ? "new" : "legacy",
      };
    }
  }
  return { chat: "legacy", visuals: "legacy" };
}

async function readRoutingLog(env, limit = 50) {
  if (env.VISUALS_ROUTING_KV) {
    const raw = await env.VISUALS_ROUTING_KV.get("routing:log:v1");
    if (raw) {
      try {
        return JSON.parse(raw).slice(-limit);
      } catch {}
    }
  }
  return [];
}

async function appendRoutingLog(env, entry) {
  const entries = await readRoutingLog(env);
  entries.push(entry);
  if (entries.length > 200) entries.splice(0, entries.length - 200);
  if (env.VISUALS_ROUTING_KV) {
    await env.VISUALS_ROUTING_KV.put("routing:log:v1", JSON.stringify(entries));
  }
}

function checkRoutingAuth(request, env) {
  const token = request.headers.get("Authorization")?.replace(/^Bearer\s+/i, "").trim() || "";
  const expected = (env.VISUALS_ROUTING_KEY || env.ADMIN_ALERT_KEY || "").trim();
  if (!expected || token !== expected) {
    return Response.json({ error: "Unauthorized" }, { status: 401, headers: { "Cache-Control": "no-store" } });
  }
  return null;
}

async function handleVisualRoutingGet(request, env) {
  const url = new URL(request.url);
  if (url.searchParams.get("mode") === "log") {
    const authError = checkRoutingAuth(request, env);
    if (authError) return authError;
    return Response.json(await readRoutingLog(env), { status: 200, headers: { "Cache-Control": "no-store" } });
  }
  const state = await readRoutingState(env);
  return Response.json({ ...state, persistent: Boolean(env.VISUALS_ROUTING_KV) }, { status: 200, headers: { "Cache-Control": "no-store" } });
}

async function handlePublicVisualsRoutingGet(request, env) {
  const state = await readRoutingState(env);
  const host = new URL(request.url).hostname.toLowerCase();
  const isPublicHost = host === "allthings140radio.online" || host === "www.allthings140radio.online";
  const selected = isPublicHost ? state.visuals : "new";
  // The shared, burn-in-tested compositor consumes the historical `chat`
  // selector. Expose a read-only adapter for the independent public Visuals
  // selector so the renderer engine remains byte-identical across Green,
  // Room and /visuals/.
  return Response.json({
    chat: selected,
    visuals: selected,
    persistent: Boolean(env.VISUALS_ROUTING_KV),
  }, { status: 200, headers: { "Cache-Control": "no-store" } });
}

async function servePublicVisuals(request, env) {
  const state = await readRoutingState(env);
  // Do not internally fetch an index.html asset here: Pages canonicalizes it
  // back to /visuals/, which would recurse through this routing decision.
  const target = state.visuals === "new" ? "/visuals/live.html" : "/visuals/legacy.html";
  const assetUrl = new URL(request.url);
  assetUrl.pathname = target;
  const response = await env.ASSETS.fetch(new Request(assetUrl, request));
  const headers = new Headers(response.headers);
  headers.set("Cache-Control", "no-store, no-cache, must-revalidate");
  headers.set("X-AT140-Visuals-Mode", state.visuals === "new" ? "live-compositor" : "legacy-hls");
  return new Response(request.method === "HEAD" ? null : response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

async function handleVisualRoutingPost(request, env, ctx) {
  if (!env.VISUALS_ROUTING_KV) {
    return Response.json({ error: "Visual routing storage unavailable" }, { status: 503, headers: { "Cache-Control": "no-store" } });
  }
  const authError = checkRoutingAuth(request, env);
  if (authError) return authError;
  let data;
  try { data = await request.json(); } catch {
    return Response.json({ error: "Invalid JSON" }, { status: 400, headers: { "Cache-Control": "no-store" } });
  }
  const validModes = ["legacy", "new"];
  const chatMode = data.chat;
  const visualsMode = data.visuals;
  if (chatMode && !validModes.includes(chatMode)) {
    return Response.json({ error: `Invalid chat mode: ${chatMode}` }, { status: 400, headers: { "Cache-Control": "no-store" } });
  }
  if (visualsMode && !validModes.includes(visualsMode)) {
    return Response.json({ error: `Invalid visuals mode: ${visualsMode}` }, { status: 400, headers: { "Cache-Control": "no-store" } });
  }
  const current = await readRoutingState(env);
  const next = { chat: chatMode || current.chat, visuals: visualsMode || current.visuals };
  if (env.VISUALS_ROUTING_KV) {
    await env.VISUALS_ROUTING_KV.put("routing:v1", JSON.stringify(next));
  }
  const logEntry = {
    action: data.action || "mode_change",
    chat: next.chat,
    visuals: next.visuals,
    changedBy: "workstation",
    timestamp: Date.now(),
    reason: data.reason || null,
  };
  ctx.waitUntil(appendRoutingLog(env, logEntry));
  return Response.json({ ok: true, state: next, log: logEntry }, { status: 200, headers: { "Cache-Control": "no-store" } });
}

async function handleVisualHealth(request, env) {
  const results = {
    ok: true,
    timestamp: Date.now(),
    vm2: { status: "unknown" },
    realtime: { status: "unknown" },
    renderer: { status: "unknown", last_ack: null, last_seen: null },
    routing: { status: "unknown" },
  };

  // 1. Check VM2 (Oracle VM 2) — is the realtime visuals server up?
  try {
    const res = await fetch(REALTIME_HEALTH_URL, {
      method: "GET",
      headers: { "Accept": "application/json" },
      cf: { timeout: 5000 },
    });
    if (res.ok) {
      const data = await res.json();
      results.vm2 = { status: "ok", ...data };
    } else {
      results.vm2 = { status: "degraded", http: res.status };
    }
  } catch (e) {
    results.vm2 = { status: "unavailable", error: String(e) };
  }

  // 2. Check realtime server health
  try {
    const res = await fetch(REALTIME_HEALTH_URL, {
      method: "GET",
      headers: { "Accept": "application/json" },
      cf: { timeout: 5000 },
    });
    if (res.ok) {
      const data = await res.json();
      results.realtime = { status: "ok", ...data };
    } else {
      results.realtime = { status: "degraded", http: res.status };
    }
  } catch (e) {
    results.realtime = { status: "unavailable", error: String(e) };
  }

  // 3. Check renderer ACK state from KV
  if (env.VISUALS_ROUTING_KV) {
    try {
      const ackRaw = await env.VISUALS_ROUTING_KV.get("renderer:last_ack", { type: "json" });
      if (ackRaw) {
        results.renderer.last_ack = ackRaw;
        const ackAge = Date.now() - (ackRaw.renderedAt || 0);
        results.renderer.last_seen = ackRaw.renderedAt
          ? new Date(ackRaw.renderedAt).toISOString()
          : null;
        results.renderer.status = ackAge < 15000 ? "fresh" : ackAge < 45000 ? "stale" : "dead";
        if (results.renderer.status === "dead") results.ok = false;
      } else {
        results.renderer = { status: "no_ack", last_ack: null, last_seen: null };
      }
    } catch {
      results.renderer = { status: "kv_error", last_ack: null, last_seen: null };
    }

    // 4. Check routing state
    const routing = await readRoutingState(env);
    results.routing = { status: "ok", state: routing };
  } else {
    results.routing = { status: "kv_unavailable" };
  }

  // Aggregate health
  if (results.vm2.status === "unavailable" || results.realtime.status === "unavailable") {
    results.ok = false;
  }
  const status = results.ok ? 200 : 503;
  return Response.json(results, { status, headers: { "Cache-Control": "no-store" } });
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if ((url.pathname === "/visuals" || url.pathname === "/visuals/") && (request.method === "GET" || request.method === "HEAD")) {
      return servePublicVisuals(request, env);
    }
    if (url.pathname === "/obs/live.mp3" && (request.method === "GET" || request.method === "HEAD")) {
      return obsAudioStream(request, env);
    }
    if (url.pathname === "/api/public/newsletter/webhook" && request.method === "POST") {
      return handleMailchimpWebhook(request, env);
    }
    if (url.pathname === "/api/public/takeover-alert" && request.method === "POST") return handleTakeoverAlert(request, env, ctx);
    if (url.pathname === "/api/visual-routing" && request.method === "GET") {
      return handleVisualRoutingGet(request, env);
    }
    if (url.pathname === "/api/visuals-routing" && request.method === "GET") {
      return handlePublicVisualsRoutingGet(request, env);
    }
    if (url.pathname === "/api/visual-routing" && request.method === "POST") {
      return handleVisualRoutingPost(request, env, ctx);
    }
    if (url.pathname === "/api/visual-health" && request.method === "GET") {
      return handleVisualHealth(request, env);
    }

    const mayProxy = request.method === "GET"
      ? PUBLIC_GET_PATH.test(url.pathname)
      : request.method === "POST" && PUBLIC_POST_PATH.test(url.pathname);

    if (url.pathname === "/api/public/newsletter/status" && request.method === "GET") {
      if (!env.MAILCHIMP_API_KEY) return Response.json({ configured: false, connected: false }, { status: 503 });
      const ping = await fetch(`https://${MAILCHIMP_SERVER}.api.mailchimp.com/3.0/ping`, { headers: { "Authorization": `Basic ${btoa(`allthings140:${env.MAILCHIMP_API_KEY}`)}` } });
      return Response.json({ configured: true, connected: ping.ok, audience: MAILCHIMP_AUDIENCE, server: MAILCHIMP_SERVER }, { status: ping.ok ? 200 : 502 });
    }

    if (url.pathname === "/api/public/newsletter" && request.method === "POST") {
      const response = await mailchimpSignup(request.clone(), env);
      if (response) return response;
    }

    if (mayProxy) {
      const upstream = new URL(url.pathname + url.search, PUBLIC_API_ORIGIN);
      const headers = new Headers(request.headers);
      headers.set("X-Client-IP", request.headers.get("CF-Connecting-IP") || "unknown");
      const response = await fetch(new Request(upstream, {
        method: request.method,
        headers,
        body: request.body,
        redirect: "follow",
      }));
      const responseHeaders = new Headers(response.headers);
      responseHeaders.set("Cache-Control", "no-store, max-age=0");
      responseHeaders.set("X-AllThings140-Proxy", "status-gateway");
      if (request.method === "POST" && url.pathname === "/api/public/takeover-interest" && response.ok) {
        const payload = await response.clone().json();
        try { await sendTakeoverInvite(payload.email, payload.link, env); }
        catch (error) { console.error("takeover_invite_email_failed", String(error)); return Response.json({ error: "We could not send the form email. Please try again." }, { status: 502 }); }
        return Response.json({ ok: true, message: "Check your email for your private takeover form." }, { status: 201 });
      }
      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: responseHeaders,
      });
    }

    const response = await env.ASSETS.fetch(request);
    if (url.pathname === "/sw.js" || url.pathname === "/sw-v47.js") {
      const headers = new Headers(response.headers);
      headers.set("Cache-Control", "no-store, no-cache, must-revalidate");
      headers.set("Service-Worker-Allowed", "/");
      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers,
      });
    }
    return response;
  },
};
