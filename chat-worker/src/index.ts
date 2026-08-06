import { DurableObject } from "cloudflare:workers";

interface Env {
  CHAT_ROOM: DurableObjectNamespace<ChatRoom>;
}

type StoredMessage = { id: string; name: string; text: string; ts: number };
type SocketState = {
  id: string;
  name: string;
  recent: number[];
  lastText: string;
  lastTextAt: number;
};

const ALLOWED_ORIGINS = new Set([
  "https://ebeinc.online",
  "https://www.ebeinc.online",
  "https://ebeinc-uqt.pages.dev",
]);
const NAME_RE = /[^\p{L}\p{N} _-]/gu;
const URL_RE = /(?:https?:\/\/|www\.)/gi;
const BLOCKED_RE = /\b(?:n[i1]gg(?:er|a)|f[a@]gg?[o0]t|k[i1]ke|ch[i1]nk)\b/gi;

function originAllowed(origin: string | null): boolean {
  if (!origin) return false;
  if (ALLOWED_ORIGINS.has(origin)) return true;
  if (/^https:\/\/[a-z0-9-]+\.ebeinc-uqt\.pages\.dev$/.test(origin)) return true;
  return /^http:\/\/(?:localhost|127\.0\.0\.1)(?::\d+)?$/.test(origin);
}

function cleanName(value: unknown, fallback: string): string {
  const clean = String(value ?? "").normalize("NFKC").replace(NAME_RE, "").replace(/\s+/g, " ").trim().slice(0, 24);
  return clean.length >= 2 ? clean : fallback;
}

function cleanMessage(value: unknown): string {
  return String(value ?? "").normalize("NFKC").replace(/[\u0000-\u001f\u007f]/g, " ").replace(/\s+/g, " ").trim().slice(0, 280);
}

function json(data: unknown, status = 200): Response {
  return Response.json(data, { status, headers: { "cache-control": "no-store" } });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/health") return json({ ok: true, service: "allthings140-live-chat" });
    if (url.pathname !== "/ws") return json({ error: "Not found" }, 404);
    if (request.headers.get("Upgrade")?.toLowerCase() !== "websocket") return json({ error: "WebSocket upgrade required" }, 426);
    if (!originAllowed(request.headers.get("Origin"))) return json({ error: "Origin not allowed" }, 403);
    return env.CHAT_ROOM.getByName("allthings140-public-v1").fetch(request);
  },
} satisfies ExportedHandler<Env>;

export class ChatRoom extends DurableObject<Env> {
  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    ctx.storage.sql.exec(`CREATE TABLE IF NOT EXISTS messages (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      text TEXT NOT NULL,
      created_at INTEGER NOT NULL
    )`);
    ctx.storage.sql.exec("CREATE INDEX IF NOT EXISTS messages_created_at ON messages(created_at)");
  }

  async fetch(request: Request): Promise<Response> {
    if (request.headers.get("Upgrade")?.toLowerCase() !== "websocket") return json({ error: "WebSocket upgrade required" }, 426);
    const pair = new WebSocketPair();
    const [client, server] = Object.values(pair);
    const id = crypto.randomUUID();
    const fallback = `Listener-${id.slice(0, 4).toUpperCase()}`;
    const state: SocketState = { id, name: fallback, recent: [], lastText: "", lastTextAt: 0 };
    server.serializeAttachment(state);
    this.ctx.acceptWebSocket(server);

    const rows = [...this.ctx.storage.sql.exec<{ id: string; name: string; text: string; created_at: number }>(
      "SELECT id, name, text, created_at FROM messages ORDER BY created_at DESC LIMIT 50"
    )].reverse();
    server.send(JSON.stringify({
      type: "history",
      messages: rows.map(row => ({ id: row.id, name: row.name, text: row.text, ts: row.created_at })),
      count: this.ctx.getWebSockets().length,
      name: fallback,
    }));
    this.broadcast({ type: "presence", count: this.ctx.getWebSockets().length });
    return new Response(null, { status: 101, webSocket: client });
  }

  async webSocketMessage(ws: WebSocket, raw: string | ArrayBuffer): Promise<void> {
    if (typeof raw !== "string" || raw.length > 2048) return this.sendError(ws, "That message is too large.");
    let body: { type?: unknown; name?: unknown; text?: unknown };
    try { body = JSON.parse(raw) as typeof body; } catch { return this.sendError(ws, "Invalid message."); }
    const state = ws.deserializeAttachment() as SocketState | null;
    if (!state) return ws.close(1011, "Missing session");

    if (body.type === "join") {
      state.name = cleanName(body.name, state.name);
      ws.serializeAttachment(state);
      ws.send(JSON.stringify({ type: "joined", name: state.name }));
      return;
    }
    if (body.type !== "message") return this.sendError(ws, "Unknown action.");

    const now = Date.now();
    state.recent = state.recent.filter(ts => now - ts < 10_000);
    if (state.recent.length >= 4 || (state.recent.at(-1) && now - state.recent.at(-1)! < 800)) {
      return this.sendError(ws, "Slow down for a moment.");
    }
    let text = cleanMessage(body.text);
    if (!text) return this.sendError(ws, "Type a message first.");
    if ((text.match(URL_RE) ?? []).length > 1) return this.sendError(ws, "Only one link is allowed per message.");
    if (text.toLocaleLowerCase() === state.lastText && now - state.lastTextAt < 30_000) return this.sendError(ws, "Please don’t repeat the same message.");
    text = text.replace(BLOCKED_RE, "***");

    const message: StoredMessage = { id: crypto.randomUUID(), name: state.name, text, ts: now };
    this.ctx.storage.sql.exec("INSERT INTO messages (id, name, text, created_at) VALUES (?, ?, ?, ?)", message.id, message.name, message.text, message.ts);
    this.ctx.storage.sql.exec("DELETE FROM messages WHERE id NOT IN (SELECT id FROM messages ORDER BY created_at DESC LIMIT 100)");
    state.recent.push(now);
    state.lastText = text.toLocaleLowerCase();
    state.lastTextAt = now;
    ws.serializeAttachment(state);
    this.broadcast({ type: "message", message });
  }

  async webSocketClose(ws: WebSocket, code: number, reason: string, wasClean: boolean): Promise<void> {
    ws.close(code, reason);
    this.broadcast({ type: "presence", count: Math.max(0, this.ctx.getWebSockets().length - (wasClean ? 0 : 1)) });
  }

  async webSocketError(ws: WebSocket): Promise<void> {
    ws.close(1011, "Connection error");
  }

  private sendError(ws: WebSocket, message: string): void {
    ws.send(JSON.stringify({ type: "error", message }));
  }

  private broadcast(payload: unknown): void {
    const data = JSON.stringify(payload);
    for (const socket of this.ctx.getWebSockets()) {
      try { socket.send(data); } catch (error) { console.warn("chat_broadcast_failed", { error: String(error) }); }
    }
  }
}
