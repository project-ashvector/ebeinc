(() => {
  "use strict";
  const dialog = document.getElementById("supportDialog");
  const form = document.getElementById("supportForm");
  if (!dialog || !form) return;
  const amount = document.getElementById("supportAmount");
  const feedback = document.getElementById("supportFeedback");
  const checkout = document.getElementById("supportCheckout");
  const checkoutView = document.getElementById("supportCheckoutView");
  const successView = document.getElementById("supportSuccessView");
  const flash = document.getElementById("supportFlash");
  const closeBtn = document.getElementById("supportClose");
  if (closeBtn) closeBtn.addEventListener("click", () => dialog.close());

  let latestSupportId = 0;
  let flashTimer = 0;

  function analytics(event, detail = {}) {
    window.dispatchEvent(new CustomEvent("allthings140:analytics", { detail: { event, ...detail } }));
    if (Array.isArray(window.dataLayer)) window.dataLayer.push({ event, ...detail });
  }

  function money(cents) {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: cents % 100 ? 2 : 0
    }).format(cents / 100);
  }

  function openSupport() {
    checkoutView.hidden = false;
    successView.hidden = true;
    feedback.textContent = "";
    if (!dialog.open) dialog.showModal();
    analytics("support_modal_opened");
    setTimeout(() => amount?.focus(), 0);
  }

  document.querySelectorAll("[data-open-support]").forEach(button =>
    button.addEventListener("click", () => {
      analytics("support_button_clicked");
      openSupport();
    })
  );

  document.querySelectorAll("[data-support-cents]").forEach(button =>
    button.addEventListener("click", () => {
      document.querySelectorAll("[data-support-cents]").forEach(item =>
        item.setAttribute("aria-pressed", String(item === button))
      );
      if (amount) amount.value = (Number(button.dataset.supportCents) / 100).toFixed(2);
      analytics("suggested_amount_selected", { amount_cents: Number(button.dataset.supportCents) });
    })
  );

  amount?.addEventListener("input", () => {
    document.querySelectorAll("[data-support-cents]").forEach(item =>
      item.setAttribute("aria-pressed", "false")
    );
  });

  form.addEventListener("submit", async event => {
    event.preventDefault();
    const cents = Math.round(Number(amount.value) * 100);
    if (!Number.isInteger(cents) || cents < 100 || cents > 100000) {
      feedback.textContent = "Choose an amount between $1 and $1,000.";
      amount.focus();
      return;
    }
    checkout.disabled = true;
    checkout.textContent = "OPENING SECURE CHECKOUT…";
    feedback.textContent = "";
    analytics("checkout_started", {
      amount_cents: cents,
      amount_type: document.querySelector('[data-support-cents][aria-pressed="true"]') ? "suggested" : "custom"
    });
    try {
      const response = await fetch("/api/public/support/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          amount_cents: cents,
          display_name: document.getElementById("supportName")?.value || "",
          message: document.getElementById("supportMessage")?.value || "",
          public_display: document.getElementById("supportPublic")?.checked ?? true
        })
      });
      const data = await response.json();
      if (!response.ok || !data.url) throw new Error(data.error || "Checkout is unavailable.");
      sessionStorage.setItem("allthings140-support-return", "1");
      location.assign(data.url);
    } catch (error) {
      feedback.textContent = error.message || "Checkout is temporarily unavailable.";
      checkout.disabled = false;
      checkout.textContent = "CONTINUE TO SECURE STRIPE CHECKOUT";
    }
  });

  function renderState(data, initial = false) {
    const goal = data.goal || {};
    const goalEl = document.getElementById("supportGoal");
    if (goalEl) goalEl.hidden = !goal.enabled;
    const titleEl = document.getElementById("supportGoalTitle");
    if (titleEl) titleEl.textContent = goal.title || "KEEP 140 ONLINE";
    const descEl = document.getElementById("supportGoalDescription");
    if (descEl) descEl.textContent = goal.description || "";
    const totalEl = document.getElementById("supportGoalTotal");
    if (totalEl) totalEl.textContent = money(Number(goal.total_cents || 0));
    const targetEl = document.getElementById("supportGoalTarget");
    if (targetEl) targetEl.textContent = money(Number(goal.target_cents || 0));

    const percent = Math.max(0, Math.min(100, (Number(goal.total_cents || 0) / Math.max(1, Number(goal.target_cents || 1))) * 100));
    const bar = document.getElementById("supportGoalBar");
    if (bar) bar.style.width = `${percent}%`;

    const feed = document.getElementById("supportFeed");
    if (feed) feed.hidden = !data.public_feed_enabled;

    const list = document.getElementById("supporterList");
    if (list && data.supporters?.length) {
      list.replaceChildren(
        ...data.supporters.map(item => {
          const li = document.createElement("li");
          const name = document.createElement("b");
          name.textContent = item.display_name || "Anonymous";
          li.append(name, ` threw ${money(item.amount_cents)} into the 140 fund`);
          if (item.message) {
            const msg = document.createElement("span");
            msg.textContent = item.message;
            li.append(msg);
          }
          return li;
        })
      );
    }

    const newest = Math.max(0, ...(data.supporters || []).map(item => Number(item.id || 0)));
    if (!initial && data.live_notifications_enabled) {
      (data.supporters || [])
        .filter(item => Number(item.id) > latestSupportId)
        .reverse()
        .forEach(showFlash);
    }
    latestSupportId = Math.max(latestSupportId, newest);
  }

  function showFlash(item) {
    if (!flash) return;
    clearTimeout(flashTimer);
    flash.textContent = `💜 ${(item.display_name || "SOMEONE").toUpperCase()} JUST THREW ${money(item.amount_cents)} INTO THE 140 FUND 💜`;
    flash.hidden = false;
    flashTimer = setTimeout(() => {
      flash.hidden = true;
    }, 6500);
  }

  async function refresh(initial = false) {
    try {
      const response = await fetch(`/api/public/support?since=${initial ? 0 : latestSupportId}`, { cache: "no-store" });
      if (response.ok) renderState(await response.json(), initial);
    } catch {}
  }

  async function showSuccess(sessionId) {
    checkoutView.hidden = true;
    successView.hidden = false;
    dialog.showModal();
    const msg = document.getElementById("supportSuccessMessage");
    if (msg) msg.textContent = "Confirming your support securely with Stripe…";
    for (let attempt = 0; attempt < 8; attempt += 1) {
      try {
        const response = await fetch(`/api/public/support/status?session_id=${encodeURIComponent(sessionId)}`, { cache: "no-store" });
        const data = await response.json();
        if (data.verified) {
          if (msg) msg.textContent = "You just helped keep the bass alive.";
          analytics("checkout_completed");
          refresh(true);
          return;
        }
      } catch {}
      await new Promise(resolve => setTimeout(resolve, Math.min(1000 + attempt * 500, 4000)));
    }
  }

  const retBtn = document.getElementById("supportReturn");
  if (retBtn) {
    retBtn.addEventListener("click", () => {
      dialog.close();
      document.getElementById("listen")?.scrollIntoView({ behavior: "smooth" });
    });
  }

  const params = new URLSearchParams(location.search);
  if (params.get("support") === "success" && params.get("session_id")) {
    showSuccess(params.get("session_id"));
  } else if (params.get("support") === "cancelled") {
    openSupport();
    feedback.textContent = "Checkout was cancelled. Nothing was charged.";
  }

  refresh(true);
  setInterval(() => {
    if (!document.hidden && navigator.onLine) refresh(false);
  }, 30000);
})();
