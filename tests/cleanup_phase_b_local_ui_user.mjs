import { execFileSync } from "node:child_process";
import { readFileSync, unlinkSync } from "node:fs";

const credentialPath = "/tmp/at140-phase-b-ui.json";
const credentials = JSON.parse(readFileSync(credentialPath, "utf8"));
const status = execFileSync(
  "npx",
  ["--offline", "--yes", "supabase@latest", "status", "-o", "env"],
  { cwd: new URL("..", import.meta.url), encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
);
const value = (name) => status.match(new RegExp(`^${name}="?([^"\\n]+)"?$`, "m"))?.[1];
const API = value("API_URL");
const ANON = value("ANON_KEY");
const SERVICE = value("SERVICE_ROLE_KEY");
if (!API || !ANON || !SERVICE) throw new Error("Local Supabase configuration unavailable");

const login = await fetch(`${API}/auth/v1/token?grant_type=password`, {
  method: "POST",
  headers: { apikey: ANON, "Content-Type": "application/json" },
  body: JSON.stringify(credentials),
});
if (!login.ok) throw new Error("Local cleanup sign-in failed");
const session = await login.json();

await fetch(`${API}/storage/v1/object/avatars/${session.user.id}/avatar`, {
  method: "DELETE",
  headers: { apikey: ANON, Authorization: `Bearer ${session.access_token}` },
});

const removed = await fetch(`${API}/auth/v1/admin/users/${session.user.id}`, {
  method: "DELETE",
  headers: { apikey: SERVICE, Authorization: `Bearer ${SERVICE}` },
});
if (!removed.ok) throw new Error("Local test user deletion failed");
unlinkSync(credentialPath);
console.log("PASS local UI test identity, avatar, and temporary credentials removed");
