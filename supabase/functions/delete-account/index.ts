import { createClient } from "https://esm.sh/@supabase/supabase-js@2.55.0";

const cors = { "access-control-allow-origin": "https://allthings140radio.online", "access-control-allow-headers": "authorization, content-type", "access-control-allow-methods": "POST, OPTIONS", "cache-control": "no-store" };
const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { ...cors, "content-type": "application/json" } });

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
  if (request.method !== "POST") return reply({ error: "method_not_allowed" }, 405);
  const authorization = request.headers.get("authorization") || "";
  if (!authorization.toLowerCase().startsWith("bearer ")) return reply({ error: "authentication_required" }, 401);
  const url = Deno.env.get("SUPABASE_URL");
  const serviceRole = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!url || !serviceRole) return reply({ error: "deletion_processor_not_configured" }, 503);
  const userClient = createClient(url, Deno.env.get("SUPABASE_ANON_KEY") || serviceRole, { global: { headers: { Authorization: authorization } } });
  const { data: { user }, error: userError } = await userClient.auth.getUser();
  if (userError || !user) return reply({ error: "invalid_session" }, 401);
  const admin = createClient(url, serviceRole);
  const { data: profile } = await admin.from("profiles").select("avatar_path").eq("id", user.id).maybeSingle();
  if (profile?.avatar_path) await admin.storage.from("avatars").remove([profile.avatar_path]);
  const { error } = await admin.auth.admin.deleteUser(user.id);
  if (error) return reply({ error: "deletion_failed" }, 500);
  return reply({ deleted: true });
});
