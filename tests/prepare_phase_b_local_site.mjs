import { cpSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";

const root = new URL("..", import.meta.url);
const target = mkdtempSync(join(tmpdir(), "at140-phase-b-site-"));
cpSync(new URL("../radio", import.meta.url), target, { recursive: true });

const status = execFileSync(
  "npx",
  ["--offline", "--yes", "supabase@latest", "status", "-o", "env"],
  { cwd: root, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
);
const value = (name) => {
  const match = status.match(new RegExp(`^${name}="?([^"\\n]+)"?$`, "m"));
  if (!match) throw new Error(`Missing local ${name}`);
  return match[1];
};

const configPath = join(target, "supabase-config.js");
const config = readFileSync(configPath, "utf8")
  .replace("https://dtvnlpgtmrbnpecsapsv.supabase.co", value("API_URL"))
  .replace(/sb_publishable_[A-Za-z0-9_-]+/, value("PUBLISHABLE_KEY"));
writeFileSync(configPath, config, { mode: 0o600 });
process.stdout.write(`${target}\n`);
