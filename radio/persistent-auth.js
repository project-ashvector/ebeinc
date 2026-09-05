(() => {
  "use strict";

  const config = window.AT140SupabaseConfig;
  const sdk = window.supabase;
  const root = document.getElementById("accountShell");
  const trigger = document.getElementById("accountTrigger");
  const triggerAvatar = document.getElementById("accountTriggerAvatar");
  const triggerLabel = document.getElementById("accountTriggerLabel");
  const dialog = document.getElementById("accountDialog");
  const closeButton = document.getElementById("accountClose");
  const signedOut = document.getElementById("accountSignedOut");
  const signedIn = document.getElementById("accountSignedIn");
  const message = document.getElementById("accountMessage");
  const profileAvatar = document.getElementById("profileAvatar");
  const profileUsername = document.getElementById("profileUsername");
  const profileIdentity = document.getElementById("profileIdentity");
  const usernameInput = document.getElementById("profileUsernameInput");
  const avatarInput = document.getElementById("profileAvatarInput");
  const profileForm = document.getElementById("profileForm");
  const plusMembership = document.getElementById("plusMembership");
  const plusMembershipCopy = document.getElementById("plusMembershipCopy");
  const plusSubscribe = document.getElementById("plusSubscribe");
  const plusManage = document.getElementById("plusManage");
  const authForms = document.getElementById("authForms");
  const tabs = [...document.querySelectorAll("[data-auth-tab]")];
  const sections = [...document.querySelectorAll("[data-auth-section]")];
  const subscribers = new Set();
  const reservedSkeletons = new Set([
    "allthings140", "allthings140radio", "admin", "administrator",
    "moderator", "mod", "system", "support", "staff",
  ]);

  let user = null;
  let profile = null;
  let roleState = null;
  let authResolved = false;
  let entitlementResolved = false;
  let authSubscription = null;
  let profileLoadGeneration = 0;
  let profileLoadingUserId = null;
  let profileQueries = 0;
  let authEvents = 0;
  let currentMode = "signin";
  let membershipStatus = null;
  let membershipLoading = false;

  if (!config || !sdk?.createClient) {
    root.hidden = true;
    console.error("ALLTHINGS140 account client failed to load.");
    return;
  }

  const client = sdk.createClient(config.url, config.publishableKey, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
      flowType: "pkce",
      storageKey: "at140-auth-session",
    },
  });

  function avatarPublicUrl(path) {
    if (!path) return null;
    return client.storage.from(config.avatarBucket).getPublicUrl(path).data.publicUrl;
  }

  function initials(name) {
    return (name || "AT").slice(0, 2).toUpperCase();
  }

  function identity() {
    if (!authResolved) return Object.freeze({ signedIn: false, authState: "AUTH_UNKNOWN", entitlementResolved: false });
    if (!user) return Object.freeze({ signedIn: false, authState: "ANONYMOUS", entitlementResolved: true, alertAdsEnabled: true });
    return Object.freeze({
      signedIn: true,
      authState: entitlementResolved
        ? (roleState?.alert_ads_enabled === false ? "AUTHENTICATED_AD_FREE" : "AUTHENTICATED_FREE")
        : "AUTH_UNKNOWN",
      entitlementResolved,
      userId: user.id,
      username: profile?.username || null,
      avatarUrl: avatarPublicUrl(profile?.avatar_path),
      accountStatus: profile?.account_status || "active",
      role: roleState?.role || "user",
      accountClass: roleState?.account_class || "regular",
      accountType: roleState?.account_type || roleState?.role || "regular",
      alertAdsPreference: roleState?.alert_ads_preference || "default",
      // A signed-in account is never treated as free until the protected RPC
      // has positively resolved its current effective entitlement.
      alertAdsEnabled: entitlementResolved ? roleState?.alert_ads_enabled === true : false,
      profileComplete: Boolean(profile?.username),
    });
  }

  function publish() {
    const value = identity();
    for (const subscriber of [...subscribers]) {
      try { subscriber(value); } catch (error) { console.error(error); }
    }
    syncRoute(document.getElementById("routeFrame")?.contentWindow);
  }

  function syncRoute(target) {
    try { target?.postMessage({ type: "AT140_IDENTITY", identity: identity() }, location.origin); } catch {}
  }

  async function sendSessionToRoute(target) {
    if (!target) return;
    const { data } = await client.auth.getSession();
    const token = data?.session?.["access_" + "token"] || null;
    try { target.postMessage({ type: "AT140_SESSION", accessToken: token }, location.origin); } catch {}
  }

  function showMessage(text, tone = "info") {
    message.textContent = text || "";
    message.dataset.tone = tone;
    message.hidden = !text;
  }

  function renderAvatar(element, name, path) {
    element.replaceChildren();
    const url = avatarPublicUrl(path);
    if (url) {
      const image = document.createElement("img");
      image.src = `${url}?v=${encodeURIComponent(profile?.updated_at || "1")}`;
      image.alt = "";
      image.referrerPolicy = "no-referrer";
      element.append(image);
    } else {
      element.textContent = initials(name);
    }
  }

  function render() {
    const loggedIn = Boolean(user);
    const recovering = dialog.open && currentMode === "recovery";
    signedOut.hidden = loggedIn && !recovering;
    signedIn.hidden = !loggedIn || recovering;
    trigger.dataset.signedIn = String(loggedIn);
    triggerLabel.textContent = loggedIn ? (profile?.username || "Complete Profile") : "ACCOUNT";
    renderAvatar(triggerAvatar, profile?.username, profile?.avatar_path);

    if (loggedIn) {
      renderAvatar(profileAvatar, profile?.username, profile?.avatar_path);
      profileUsername.textContent = profile?.username || "Profile setup required";
      profileIdentity.textContent = `Account ID ${user.id}`;
      document.getElementById("profileHeroEmail").textContent = roleState?.email || user.email || "—";
      usernameInput.value = profile?.username || "";
      usernameInput.disabled = profile?.account_status !== "active";
      document.getElementById("profileStatus").textContent = (profile?.account_status || "active").toUpperCase();
      document.getElementById("profileEmail").textContent = roleState?.email || user.email || "—";
      document.getElementById("profileRole").textContent = (roleState?.role || "user").toUpperCase();
      const role = roleState?.role || "user";
      const badge = document.getElementById("accountRoleBadge");
      const accountType = roleState?.account_type || "regular";
      badge.hidden = accountType === "regular";
      badge.textContent = accountType === "partner_sponsor" ? "PARTNER" : accountType === "moderator" ? "MOD" : accountType.toUpperCase();
      badge.dataset.role = accountType;
      document.getElementById("profileAccountType").textContent = accountType === "partner_sponsor" ? "PARTNER / SPONSOR" : accountType.toUpperCase();
      const adsOn = roleState?.alert_ads_enabled === true;
      document.getElementById("profileAlertAds").textContent = adsOn ? "ON" : "OFF";
      const benefit = accountType === "plus" ? "Included with Plus" : accountType === "resident" ? "ALLTHINGS140 Resident benefit" : accountType === "partner_sponsor" ? "Partner benefit" : accountType === "moderator" ? "Staff account" : accountType === "admin" ? "Administrator account" : "Included in the shared station stream";
      document.getElementById("profileAlertNote").textContent = accountType === "regular" ? "Regular accounts include station alerts." : `${benefit} — disabled by your account`;
      const purchasable = ["regular", "plus"].includes(accountType);
      const stripeMembership = membershipStatus?.subscriptions?.some(item => item.provider === "stripe");
      plusMembership.hidden = !purchasable;
      plusSubscribe.hidden = accountType !== "regular" || membershipStatus?.plus === true;
      plusManage.hidden = !stripeMembership;
      plusSubscribe.disabled = membershipLoading;
      plusManage.disabled = membershipLoading;
      plusMembershipCopy.textContent = accountType === "plus"
        ? (stripeMembership ? "PLUS is active. Manage renewal, payment method, or cancellation in Stripe’s secure portal." : "PLUS is active on this account.")
        : "Automatically renews monthly until canceled. Cancel anytime from the secure billing portal.";
      for (const item of document.querySelectorAll("[data-min-role]")) {
        item.hidden = item.dataset.minRole === "admin" ? role !== "admin" : !["moderator", "admin"].includes(role);
      }
      document.getElementById("profileTermsState").textContent = "PENDING LEGAL/UGC PHASE";
      document.getElementById("profileCooldown").textContent = profile?.username
        ? `Username changes are limited to once every ${config.usernameCooldownDays} days.`
        : "Your first username can be chosen now.";
    }
    publish();
  }

  async function billingRequest(path, method = "GET") {
    const { data } = await client.auth.getSession();
    const token = data?.session?.["access_" + "token"];
    if (!token) throw new Error("Sign in is required.");
    const response = await fetch(path, { method, headers: { Authorization: `Bearer ${token}`, Accept: "application/json" } });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.error || "Membership service is temporarily unavailable.");
    return body;
  }

  async function refreshMembershipStatus() {
    if (!user || membershipLoading) return;
    membershipLoading = true;
    render();
    try { membershipStatus = await billingRequest("/api/account/plus/status"); }
    catch (error) { console.warn("PLUS status unavailable", String(error)); }
    finally { membershipLoading = false; render(); }
  }

  async function openBilling(action) {
    if (membershipLoading) return;
    membershipLoading = true;
    render();
    showMessage(action === "checkout" ? "Opening secure PLUS checkout…" : "Opening secure billing portal…");
    try {
      const result = await billingRequest(`/api/account/plus/${action}`, "POST");
      if (!String(result.url || "").startsWith("https://")) throw new Error("Secure billing URL was not returned.");
      location.assign(result.url);
    } catch (error) {
      membershipLoading = false;
      render();
      showMessage(String(error.message || error), "error");
    }
  }

  async function loadProfile(expectedUser) {
    if (profileLoadingUserId === expectedUser.id) return;
    profileLoadingUserId = expectedUser.id;
    const generation = ++profileLoadGeneration;
    profileQueries += 1;
    const [{ data, error }, roleResult] = await Promise.all([
      client.from("profiles").select("id,username,avatar_path,created_at,updated_at,account_status").eq("id", expectedUser.id).maybeSingle(),
      client.rpc("account_role_state"),
    ]);
    if (generation !== profileLoadGeneration || user?.id !== expectedUser.id) return;
    profileLoadingUserId = null;
    if (error) {
      profile = null;
      showMessage("Your session is active, but the profile could not be loaded.", "error");
    } else {
      profile = data;
      if (!profile?.username) openDialog("profile");
    }
    if (!roleResult.error) {
      const resolvedRole = Array.isArray(roleResult.data) ? roleResult.data[0] || null : roleResult.data;
      if (resolvedRole) {
        roleState = resolvedRole;
        entitlementResolved = true;
        console.info(`[ADS] auth resolved role=${resolvedRole.account_type || resolvedRole.role || "regular"} enabled=${resolvedRole.alert_ads_enabled === true}`);
      }
    }
    if (!entitlementResolved) console.warn("[ADS] scheduler disabled reason=authority_unknown");
    render();
    void refreshMembershipStatus();
  }

  function applySession(session, forceAuthorityRefresh = false) {
    const nextUser = session?.user || null;
    authResolved = true;
    if (nextUser?.id === user?.id && profile && !forceAuthorityRefresh) {
      render();
      return;
    }
    user = nextUser;
    profile = null;
    roleState = null;
    membershipStatus = null;
    entitlementResolved = !user;
    if (forceAuthorityRefresh) profileLoadingUserId = null;
    if (user) loadProfile(user);
    else {
      profileLoadGeneration += 1;
      profileLoadingUserId = null;
      render();
    }
  }

  function setMode(mode) {
    currentMode = mode;
    const authenticatedMode = mode === "profile";
    const recoveryMode = mode === "recovery";
    authForms.hidden = authenticatedMode;
    signedIn.hidden = !authenticatedMode;
    signedOut.hidden = authenticatedMode;
    document.querySelector(".auth-tabs").hidden = recoveryMode;
    for (const tab of tabs) tab.setAttribute("aria-selected", String(tab.dataset.authTab === mode));
    for (const section of sections) section.hidden = section.dataset.authSection !== mode;
    showMessage("");
  }

  function openDialog(mode = user ? "profile" : "signin") {
    setMode(mode);
    if (!dialog.open) dialog.showModal();
    requestAnimationFrame(() => dialog.querySelector("input:not([disabled]),button")?.focus());
  }

  function closeDialog() {
    if (dialog.open) dialog.close();
  }

  function validateUsername(value) {
    const username = value.trim();
    if (username.length < config.usernameMin || username.length > config.usernameMax) return "Use 3–24 characters.";
    if (!/^[A-Za-z0-9_]+$/.test(username)) return "Use letters, numbers, and underscores only.";
    const skeleton = username.toLowerCase().replace(/[^a-z0-9]/g, "");
    if (reservedSkeletons.has(skeleton)) return "That identity is reserved.";
    return null;
  }

  async function processAvatar(file) {
    if (!file) return null;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) throw new Error("Choose a JPEG, PNG, or WebP image.");
    if (file.size > 8 * 1024 * 1024) throw new Error("The source image must be 8 MB or smaller.");
    const bitmap = await createImageBitmap(file);
    const size = Math.min(512, bitmap.width, bitmap.height);
    const canvas = document.createElement("canvas");
    canvas.width = 512;
    canvas.height = 512;
    const context = canvas.getContext("2d", { alpha: false });
    const sx = (bitmap.width - size) / 2;
    const sy = (bitmap.height - size) / 2;
    context.drawImage(bitmap, sx, sy, size, size, 0, 0, 512, 512);
    bitmap.close();
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/webp", 0.86));
    if (!blob || blob.size > config.maxAvatarBytes) throw new Error("The processed avatar exceeds the 2 MB limit.");
    return blob;
  }

  async function saveProfile(event) {
    event.preventDefault();
    if (!user) return;
    const username = usernameInput.value.trim();
    const validation = validateUsername(username);
    if (validation) return showMessage(validation, "error");
    showMessage("Saving profile…");
    try {
      let avatarPath = profile?.avatar_path || null;
      const avatar = await processAvatar(avatarInput.files[0]);
      if (avatar) {
        avatarPath = `${user.id}/avatar`;
        const { error: uploadError } = await client.storage
          .from(config.avatarBucket)
          .upload(avatarPath, avatar, { contentType: "image/webp", upsert: true, cacheControl: "3600" });
        if (uploadError) throw uploadError;
      }
      const { data, error } = await client
        .from("profiles")
        .update({ username, avatar_path: avatarPath })
        .eq("id", user.id)
        .select("id,username,avatar_path,created_at,updated_at,account_status")
        .single();
      if (error) throw error;
      profile = data;
      avatarInput.value = "";
      showMessage("Profile saved.", "success");
      render();
    } catch (error) {
      const code = String(error?.message || error);
      const friendly = code.includes("profiles_username_casefold_unique") || code.includes("duplicate key")
        ? "That username is already taken."
        : code.includes("username_cooldown")
          ? `Username changes are limited to once every ${config.usernameCooldownDays} days.`
          : code.includes("username_reserved")
            ? "That identity is reserved."
            : "Profile could not be saved. Check the fields and try again.";
      showMessage(friendly, "error");
    }
  }

  async function submitEmail(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const email = form.elements.email.value.trim();
    const password = form.elements.password?.value || "";
    if (currentMode === "signup" && password !== form.elements.confirmPassword?.value) return showMessage("Passwords do not match.", "error");
    showMessage(currentMode === "signup" ? "Creating account…" : "Signing in…");
    const redirectTo = `${location.origin}${location.pathname}`;
    const result = currentMode === "signup"
      ? await client.auth.signUp({ email, password, options: { emailRedirectTo: redirectTo } })
      : await client.auth.signInWithPassword({ email, password });
    if (result.error) return showMessage(result.error.message, "error");
    form.reset();
    if (currentMode === "signup" && !result.data.session) {
      showMessage("Check your email to verify the account, then return here to complete your profile.", "success");
    } else {
      showMessage("Signed in.", "success");
    }
  }

  async function requestReset(event) {
    event.preventDefault();
    const email = event.currentTarget.elements.email.value.trim();
    showMessage("Sending reset instructions…");
    const { error } = await client.auth.resetPasswordForEmail(email, {
      redirectTo: `${location.origin}${location.pathname}?account=recovery`,
    });
    if (error) showMessage(error.message, "error");
    else showMessage("If that account exists, password reset instructions are on the way.", "success");
  }

  async function updatePassword(event) {
    event.preventDefault();
    const password = event.currentTarget.elements.password.value;
    if (password !== event.currentTarget.elements.confirmPassword.value) return showMessage("Passwords do not match.", "error");
    showMessage("Updating password…");
    const { error } = await client.auth.updateUser({ password });
    if (error) showMessage(error.message, "error");
    else {
      event.currentTarget.reset();
      setMode("profile");
      showMessage("Password updated.", "success");
    }
  }

  async function startOAuth(provider) {
    const enabled = provider === "google" ? config.googleEnabled : config.soundCloudEnabled;
    if (!enabled) return showMessage(`${provider === "google" ? "Google" : "SoundCloud"} provider configuration is still required.`, "info");
    const { error } = await client.auth.signInWithOAuth({
      provider: provider === "soundcloud" ? "custom:soundcloud" : provider,
      options: { redirectTo: `${location.origin}${location.pathname}` },
    });
    if (error) showMessage(error.message, "error");
  }

  trigger.addEventListener("click", () => openDialog());
  closeButton.addEventListener("click", closeDialog);
  dialog.addEventListener("click", (event) => { if (event.target === dialog) closeDialog(); });
  for (const button of document.querySelectorAll("[data-open-auth]")) button.addEventListener("click", () => openDialog(button.dataset.openAuth));
  for (const tab of tabs) tab.addEventListener("click", () => setMode(tab.dataset.authTab));
  for (const button of document.querySelectorAll("[data-auth-switch]")) button.addEventListener("click", () => setMode(button.dataset.authSwitch));
  for (const button of document.querySelectorAll("[data-password-toggle]")) button.addEventListener("click", () => {
    const input = button.previousElementSibling;
    const reveal = input.type === "password";
    input.type = reveal ? "text" : "password";
    button.textContent = reveal ? "Hide" : "Show";
    button.setAttribute("aria-label", `${reveal ? "Hide" : "Show"} password`);
  });
  document.getElementById("signInForm").addEventListener("submit", submitEmail);
  document.getElementById("signUpForm").addEventListener("submit", submitEmail);
  document.getElementById("resetForm").addEventListener("submit", requestReset);
  document.getElementById("recoveryForm").addEventListener("submit", updatePassword);
  profileForm.addEventListener("submit", saveProfile);
  plusSubscribe.addEventListener("click", () => openBilling("checkout"));
  plusManage.addEventListener("click", () => openBilling("portal"));
  document.getElementById("googleAuth").addEventListener("click", () => startOAuth("google"));
  document.getElementById("soundCloudAuth").addEventListener("click", () => startOAuth("soundcloud"));
  document.getElementById("oauthOptions").hidden = !(config.googleEnabled || config.soundCloudEnabled);
  document.getElementById("googleAuth").hidden = !config.googleEnabled;
  document.getElementById("soundCloudAuth").hidden = !config.soundCloudEnabled;
  document.getElementById("accountSignOut").addEventListener("click", async () => {
    const { error } = await client.auth.signOut();
    if (error) showMessage(error.message, "error");
    else closeDialog();
  });
  document.getElementById("requestDeletion").addEventListener("click", async () => {
    if (!confirm("Submit an account-deletion request? This is intended to be permanent.")) return;
    const { data } = await client.auth.getSession();
    const token = data?.session?.["access_" + "token"];
    try {
      const response = await fetch(`${config.url}/functions/v1/delete-account`, { method: "POST", headers: { Authorization: `Bearer ${token}`, "content-type": "application/json" } });
      const body = await response.json().catch(() => ({}));
      showMessage(response.ok && body.deleted ? "Account deletion completed." : "Account deletion is temporarily unavailable; please try again later.", response.ok && body.deleted ? "success" : "error");
      if (response.ok && body.deleted) await client.auth.signOut();
    } catch (_) { showMessage("Account deletion is temporarily unavailable; please try again later.", "error"); }
  });

  window.AT140Auth = Object.freeze({
    identity,
    accessToken: async () => (await client.auth.getSession()).data?.session?.["access_" + "token"] || null,
    open: openDialog,
    rpc: (name, parameters = {}) => client.rpc(name, parameters),
    avatarUrl: avatarPublicUrl,
    async refreshRole() {
      if (!user) return identity();
      const expectedUserId = user.id;
      const expectedGeneration = profileLoadGeneration;
      const result = await client.rpc("account_role_state");
      if (user?.id !== expectedUserId || profileLoadGeneration !== expectedGeneration) return identity();
      if (!result.error) {
        const resolvedRole = Array.isArray(result.data) ? result.data[0] || null : result.data;
        if (resolvedRole) {
          roleState = resolvedRole;
          entitlementResolved = true;
        }
      }
      render();
      return identity();
    },
    syncRoute,
    subscribe(callback) {
      subscribers.add(callback);
      callback(identity());
      return () => subscribers.delete(callback);
    },
    inspect() {
      return Object.freeze({
        authorities: 1,
        authListeners: authSubscription ? 1 : 0,
        subscribers: subscribers.size,
        profileQueries,
        authEvents,
        signedIn: Boolean(user),
        userId: user?.id || null,
        profileComplete: Boolean(profile?.username),
      });
    },
  });

  window.addEventListener("message", (event) => {
    if (event.origin !== location.origin) return;
    if (event.data?.type === "AT140_REQUEST_SESSION") void sendSessionToRoute(event.source);
    if (event.data?.type === "AT140_OPEN_AUTH") openDialog(event.data.mode || "signin");
  });

  const requestedMode = window.AT140InitialAccountMode || new URLSearchParams(location.search).get("account");
  if (["signin", "signup", "reset"].includes(requestedMode)) openDialog(requestedMode);
  client.auth.getSession().then(({ data, error }) => {
    if (error) showMessage("The saved session could not be restored.", "error");
    applySession(data?.session || null);
  });
  const authChange = client.auth.onAuthStateChange((event, session) => {
    authEvents += 1;
    setTimeout(() => {
      applySession(session, event === "TOKEN_REFRESHED" || event === "USER_UPDATED");
      if (event === "PASSWORD_RECOVERY") openDialog("recovery");
    }, 0);
  });
  authSubscription = authChange.data.subscription;
  // Subscription expiry and staff/account-class changes take effect without a
  // reload even when Supabase emits no auth event for the database change.
  setInterval(() => { if (user) void window.AT140Auth.refreshRole(); }, 5 * 60 * 1000);
  render();
})();
