interface Env {
  ARCHIVES: R2Bucket;
  UPLOAD_TOKEN: string;
}

const OBJECT_PATH = /^\/objects\/([a-zA-Z0-9][a-zA-Z0-9._\/-]{1,300})$/;

function reply(body: BodyInit | null, status: number, headers: HeadersInit = {}) {
  return new Response(body, { status, headers: { "Cache-Control": "no-store", ...headers } });
}

async function authorized(request: Request, secret: string) {
  const supplied = request.headers.get("Authorization")?.replace(/^Bearer\s+/i, "") || "";
  if (!supplied || !secret) return false;
  const encoder = new TextEncoder();
  const [a, b] = await Promise.all([
    crypto.subtle.digest("SHA-256", encoder.encode(supplied)),
    crypto.subtle.digest("SHA-256", encoder.encode(secret)),
  ]);
  const left = new Uint8Array(a), right = new Uint8Array(b);
  let difference = left.length ^ right.length;
  for (let index = 0; index < left.length; index++) difference |= left[index] ^ right[index];
  return difference === 0;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/health") return Response.json({ ok: true, service: "allthings140-archive-gateway" });
    const match = url.pathname.match(OBJECT_PATH);
    if (!match || match[1].includes("..")) return reply("Not found", 404);
    const key = match[1];

    if (request.method === "PUT") {
      if (!await authorized(request, env.UPLOAD_TOKEN)) return reply("Unauthorized", 401);
      const length = Number(request.headers.get("Content-Length") || 0);
      if (!request.body || length > 5 * 1024 * 1024 * 1024) return reply("Invalid object", 400);
      await env.ARCHIVES.put(key, request.body, {
        httpMetadata: { contentType: request.headers.get("Content-Type") || "application/octet-stream" },
        customMetadata: { source: "allthings140radio-server" },
      });
      return Response.json({ ok: true, key }, { status: 201 });
    }

    if (request.method !== "GET" && request.method !== "HEAD") return reply("Method not allowed", 405, { Allow: "GET, HEAD, PUT" });
    const object = await env.ARCHIVES.get(key);
    if (!object) return reply("Not found", 404);
    const headers = new Headers();
    object.writeHttpMetadata(headers);
    headers.set("ETag", object.httpEtag);
    headers.set("Cache-Control", "public, max-age=3600");
    headers.set("Access-Control-Allow-Origin", "*");
    headers.set("Accept-Ranges", "bytes");
    return new Response(request.method === "HEAD" ? null : object.body, { headers });
  },
} satisfies ExportedHandler<Env>;
