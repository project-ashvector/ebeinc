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
  let authSubscription = null;
  let profileLoadGeneration = 0;
  let profileLoadingUserId = null;
  let profileQueries = 0;
  let authEvents = 0;
  let currentMode = "signin";

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
    if (!user) return Object.freeze({ signedIn: false });
    return Object.freeze({
      signedIn: true,
      userId: user.id,
      username: profile?.username || null,
      avatarUrl: avatarPublicUrl(profile?.avatar_path),
      accountStatus: profile?.account_status || "active",
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
      usernameInput.value = profile?.username || "";
      usernameInput.disabled = profile?.account_status !== "active";
      document.getElementById("profileStatus").textContent = (profile?.account_status || "active").toUpperCase();
      document.getElementById("profileTermsState").textContent = "PENDING LEGAL/UGC PHASE";
      document.getElementById("profileCooldown").textContent = profile?.username
        ? `Username changes are limited to once every ${config.usernameCooldownDays} days.`
        : "Your first username can be chosen now.";
    }
    publish();
  }

  async function loadProfile(expectedUser) {
    if (profileLoadingUserId === expectedUser.id) return;
    profileLoadingUserId = expectedUser.id;
    const generation = ++profileLoadGeneration;
    profileQueries += 1;
    const { data, error } = await client
      .from("profiles")
      .select("id,username,avatar_path,created_at,updated_at,account_status")
      .eq("id", expectedUser.id)
      .maybeSingle();
    if (generation !== profileLoadGeneration || user?.id !== expectedUser.id) return;
    profileLoadingUserId = null;
    if (error) {
      profile = null;
      showMessage("Your session is active, but the profile could not be loaded.", "error");
    } else {
      profile = data;
      if (!profile?.username) openDialog("profile");
    }
    render();
  }

  function applySession(session) {
    const nextUser = session?.user || null;
    if (nextUser?.id === user?.id && profile) {
      render();
      return;
    }
    user = nextUser;
    profile = null;
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
    authForms.hidden = authenticatedMode;
    signedIn.hidden = !authenticatedMode;
    signedOut.hidden = authenticatedMode;
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
  document.getElementById("signInForm").addEventListener("submit", submitEmail);
  document.getElementById("signUpForm").addEventListener("submit", submitEmail);
  document.getElementById("resetForm").addEventListener("submit", requestReset);
  document.getElementById("recoveryForm").addEventListener("submit", updatePassword);
  profileForm.addEventListener("submit", saveProfile);
  document.getElementById("googleAuth").addEventListener("click", () => startOAuth("google"));
  document.getElementById("soundCloudAuth").addEventListener("click", () => startOAuth("soundcloud"));
  document.getElementById("accountSignOut").addEventListener("click", async () => {
    const { error } = await client.auth.signOut();
    if (error) showMessage(error.message, "error");
    else closeDialog();
  });
  document.getElementById("requestDeletion").addEventListener("click", async () => {
    if (!confirm("Queue a secure account-deletion request? Your account is not deleted immediately.")) return;
    const { error } = await client.rpc("request_my_account_deletion");
    showMessage(error ? "Deletion request could not be queued." : "Deletion request queued for secure server processing.", error ? "error" : "success");
  });

  window.AT140Auth = Object.freeze({
    identity,
    open: openDialog,
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

  client.auth.getSession().then(({ data, error }) => {
    if (error) showMessage("The saved session could not be restored.", "error");
    applySession(data?.session || null);
  });
  const authChange = client.auth.onAuthStateChange((event, session) => {
    authEvents += 1;
    setTimeout(() => {
      applySession(session);
      if (event === "PASSWORD_RECOVERY") openDialog("recovery");
    }, 0);
  });
  authSubscription = authChange.data.subscription;
  render();
})();
