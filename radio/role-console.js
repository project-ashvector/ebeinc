(() => {
  "use strict";
  const auth = window.AT140Auth;
  if (!auth) return;
  const nav = [...document.querySelectorAll("#accountNav [data-account-view]")];
  const panels = [...document.querySelectorAll("[data-account-view-panel]")];
  const reportsRoot = document.getElementById("moderationReports");
  const actionsRoot = document.getElementById("moderationActions");
  const adminRoot = document.getElementById("adminResults");
  const adminAuditRoot = document.getElementById("adminAudit");
  let identity = { signedIn: false, role: "user" };

  const node = (tag, className, text) => { const el = document.createElement(tag); if (className) el.className = className; if (text != null) el.textContent = text; return el; };
  const empty = (root, text) => root.replaceChildren(node("div", "staff-empty", text));
  const rpc = async (name, args = {}) => { const result = await auth.rpc(name, args); if (result.error) throw new Error(result.error.message || "Request denied"); return result.data; };
  const rows = value => Array.isArray(value) ? value : value ? [value] : [];
  const stamp = value => value ? new Date(value).toLocaleString() : "Unknown time";
  const requireConfirm = (action, target) => confirm(`${action}\n\nTarget: ${target}\n\nThis server-authorized action is recorded in the audit log.`);
  const readableAction = action => ({ moderator_assign: "Moderator assigned", moderator_remove: "Moderator removed", account_class_assign: "Account type changed", ban: "Account banned", unban: "Account restored", resolve: "Report resolved", dismiss: "Report dismissed", delete: "Message deleted", MESSAGE_DELETE: "Message deleted", REPORT_RESOLVE: "Report resolved", REPORT_DISMISS: "Report dismissed" }[action] || String(action || "Protected action").replaceAll("_", " ").toLowerCase().replace(/^./, value => value.toUpperCase()));

  function showView(name) {
    if (name === "admin" && identity.role !== "admin") return;
    if (name === "moderation" && !["moderator", "admin"].includes(identity.role)) return;
    for (const item of nav) item.setAttribute("aria-current", item.dataset.accountView === name ? "page" : "false");
    for (const panel of panels) panel.hidden = panel.dataset.accountViewPanel !== name;
    if (name === "moderation") void loadModeration();
    if (name === "admin") void loadAdminAudit();
  }

  function actionButton(text, callback, danger = false) {
    const button = node("button", "", text); button.type = "button"; if (danger) button.dataset.danger = "true";
    button.addEventListener("click", async () => { button.disabled = true; try { await callback(); } catch (error) { alert(error.message || "Action failed"); } finally { button.disabled = false; } });
    return button;
  }

  async function deleteMessage(report) {
    const snapshot = report.message_snapshot || {}, target = snapshot.name || report.reported_user_id || "reported user";
    if (!requireConfirm("DELETE GREEN ROOM MESSAGE", target)) return;
    const token = await auth.accessToken();
    await new Promise((resolve, reject) => {
      const socket = new WebSocket("wss://chat.ebeinc.online/ws"); let authenticated = false;
      const timer = setTimeout(() => { socket.close(); reject(new Error("Green Room moderation timed out.")); }, 9000);
      socket.onopen = () => socket.send(JSON.stringify({ type: "auth", accessToken: token }));
      socket.onmessage = event => { const data = JSON.parse(event.data); if (data.type === "auth_state" && data.moderator) { authenticated = true; socket.send(JSON.stringify({ type: "moderate", action: "delete", messageId: report.message_id, targetUserId: report.reported_user_id, reason: report.reason })); setTimeout(() => { clearTimeout(timer); socket.close(); resolve(); }, 400); } else if (data.type === "error" && !authenticated) { clearTimeout(timer); socket.close(); reject(new Error(data.message)); } };
      socket.onerror = () => { clearTimeout(timer); reject(new Error("Green Room moderation connection failed.")); };
    });
  }

  function reportCard(report) {
    const snapshot = report.message_snapshot || {}, title = snapshot.name || report.reported_user_id || "Unknown account";
    const card = node("article", "staff-card"); const head = node("header"); head.append(node("h4", "", title), node("span", "staff-meta", String(report.status || "pending").toUpperCase()));
    card.append(head, node("p", "", snapshot.text || "Message evidence unavailable."), node("div", "staff-meta", `${String(report.reason || "other").toUpperCase()} • ${stamp(report.created_at)}`));
    const buttons = node("div", "staff-actions");
    buttons.append(
      actionButton("DELETE MESSAGE", async () => { await deleteMessage(report); await rpc("green_room_resolve_report", { p_report_id: report.id, p_status: "resolved", p_action: "MESSAGE_DELETE", p_notes: "Deleted from moderation queue" }); await loadModeration(); }, true),
      actionButton("RESOLVE", async () => { if (!requireConfirm("RESOLVE REPORT", title)) return; await rpc("green_room_resolve_report", { p_report_id: report.id, p_status: "resolved", p_action: "REPORT_RESOLVE", p_notes: "Resolved by moderator" }); await loadModeration(); }),
      actionButton("DISMISS", async () => { if (!requireConfirm("DISMISS REPORT", title)) return; await rpc("green_room_resolve_report", { p_report_id: report.id, p_status: "dismissed", p_action: "REPORT_DISMISS", p_notes: "Dismissed by moderator" }); await loadModeration(); }),
      actionButton("BAN USER", async () => { if (!requireConfirm("BAN ACCOUNT", title)) return; await rpc("green_room_set_account_status", { p_user_id: report.reported_user_id, p_status: "banned", p_reason: `Report ${report.id}` }); await loadModeration(); }, true),
      actionButton("UNBAN / RESTORE", async () => { if (!requireConfirm("RESTORE ACCOUNT", title)) return; await rpc("green_room_set_account_status", { p_user_id: report.reported_user_id, p_status: "active", p_reason: `Moderator restore after report ${report.id}` }); await loadModeration(); })
    ); card.append(buttons); return card;
  }

  async function loadModeration() {
    if (!["moderator", "admin"].includes(identity.role)) return;
    empty(reportsRoot, "Loading pending reports…");
    try { const reports = rows(await rpc("green_room_moderator_reports", { p_status: "pending" })); reportsRoot.replaceChildren(...(reports.length ? reports.map(reportCard) : [node("div", "staff-empty", "No pending reports.")])); }
    catch (error) { empty(reportsRoot, `Moderation unavailable: ${error.message}`); }
    try { const actions = rows(await rpc("moderator_recent_actions", { p_limit: 50 })); actionsRoot.replaceChildren(...(actions.length ? actions.map(action => { const card=node("article","staff-card"); card.append(node("h4","",String(action.action||"").replaceAll("_"," ").toUpperCase()),node("p","",`${action.actor_username || action.actor_user_id} → ${action.target_username || action.target_user_id || "community"}`),node("div","staff-meta",`${stamp(action.created_at)}${action.reason ? ` • ${action.reason}` : ""}`)); return card; }) : [node("div","staff-empty","No moderation actions recorded.")])); }
    catch (error) { empty(actionsRoot, `Audit history unavailable: ${error.message}`); }
  }

  function userCard(user) {
    const title = user.username || "Profile incomplete", role = user.role || "user", status = user.account_status || "active", accountType=user.account_type||"regular";
    const card=node("article","staff-card"), head=node("header"), label=accountType==="partner_sponsor"?"PARTNER":accountType==="moderator"?"MOD":accountType.toUpperCase(), identityRoot=node("div","staff-identity");
    if(user.avatar_path){const avatar=node("img","staff-avatar");avatar.src=auth.avatarUrl(user.avatar_path);avatar.alt="";identityRoot.append(avatar);} identityRoot.append(node("h4","",title));head.append(identityRoot,node("span","role-badge",label));
    const summary=node("div","staff-summary"); for(const [key,value] of [["STATUS",status.toUpperCase()],["SECURITY ROLE",role.toUpperCase()],["ALERT ENTITLEMENT",user.alert_ads_enabled?"ON":"OFF — MIGRATION PENDING"]]){const item=node("span");item.append(node("small","",key),node("b","",value));summary.append(item);} card.append(head,node("p","",user.email || "Email unavailable"),summary);
    const buttons=node("div","staff-actions");
    if(role!=="admin") for(const [value,labelText] of [["regular","REGULAR"],["plus","TEST PLUS"],["resident","RESIDENT"],["partner_sponsor","PARTNER / SPONSOR"]]) buttons.append(actionButton(`SET ${labelText}`,async()=>{if(!requireConfirm(`SET ACCOUNT TYPE: ${labelText}`,title))return;await rpc("admin_set_account_class",{p_user_id:user.user_id,p_account_class:value,p_source:value==="plus"?"manual_test":"admin",p_reason:"Admin account console"});await lookup();}));
    if (role === "moderator") buttons.append(actionButton("REMOVE MODERATOR",async()=>{if(!requireConfirm("REMOVE MODERATOR",title))return;await rpc("admin_remove_moderator",{p_user_id:user.user_id,p_reason:"Admin account console"});await lookup();},true));
    else if (role !== "admin") buttons.append(actionButton("ASSIGN MODERATOR",async()=>{if(!requireConfirm("ASSIGN MODERATOR",title))return;await rpc("admin_assign_moderator",{p_user_id:user.user_id,p_reason:"Admin account console"});await lookup();}));
    if (status === "banned") buttons.append(actionButton("UNBAN",async()=>{if(!requireConfirm("UNBAN ACCOUNT",title))return;await rpc("green_room_set_account_status",{p_user_id:user.user_id,p_status:"active",p_reason:"Admin account console"});await lookup();}));
    else if (role !== "admin") buttons.append(actionButton("BAN",async()=>{if(!requireConfirm("BAN ACCOUNT",title))return;await rpc("green_room_set_account_status",{p_user_id:user.user_id,p_status:"banned",p_reason:"Admin account console"});await lookup();},true));
    card.append(buttons); return card;
  }

  async function lookup() { const query=document.getElementById("adminLookupQuery").value.trim(); if(query.length<2)return; empty(adminRoot,"Searching…"); try{const users=rows(await rpc("admin_lookup_user",{p_query:query}));adminRoot.replaceChildren(...(users.length?users.map(userCard):[node("div","staff-empty","No matching users.")]));}catch(error){empty(adminRoot,`Lookup denied: ${error.message}`);} }

  function auditCard(action) { const card=node("article","staff-card audit-action"), target=action.target_username || "community"; card.append(node("h4","",`${readableAction(action.action)}${target ? ` • ${target}` : ""}`),node("p","",action.reason || "Protected server-authorized action"),node("div","staff-meta",`${action.actor_username || "Staff"} • ${stamp(action.created_at)}`)); return card; }
  async function loadAdminAudit(){ if(identity.role!=="admin")return;empty(adminAuditRoot,"Loading audit history…");try{const actions=rows(await rpc("moderator_recent_actions",{p_limit:75}));adminAuditRoot.replaceChildren(...(actions.length?actions.map(auditCard):[node("div","staff-empty","No protected actions recorded.")]));}catch(error){empty(adminAuditRoot,`Audit history unavailable: ${error.message}`);} }

  for (const item of nav) item.addEventListener("click", async () => { identity = await auth.refreshRole(); showView(item.dataset.accountView); });
  document.getElementById("refreshModeration").addEventListener("click", loadModeration);
  document.getElementById("adminLookupForm").addEventListener("submit", event => { event.preventDefault(); void lookup(); });
  document.getElementById("refreshAdminAudit").addEventListener("click", loadAdminAudit);
  for (const tab of document.querySelectorAll("[data-mod-tab]")) tab.addEventListener("click",()=>{const reports=tab.dataset.modTab==="reports";reportsRoot.hidden=!reports;actionsRoot.hidden=reports;for(const item of document.querySelectorAll("[data-mod-tab]"))item.setAttribute("aria-current",item===tab?"page":"false");});
  document.addEventListener("visibilitychange",()=>{if(!document.hidden&&identity.signedIn)void auth.refreshRole();});
  auth.subscribe(value => { identity=value; if(!value.signedIn)showView("profile"); });
})();
