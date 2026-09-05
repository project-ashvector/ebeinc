(() => {
  const form = document.getElementById("takeoverApplicationForm");
  if (!form) return;
  const feedback = document.getElementById("takeoverApplicationFeedback");
  const format = form.elements.submission_type;
  const recording = form.elements.recording_url;
  const duration = form.elements.duration_minutes;
  const updateRecorded = () => {
    const required = format.value === "recorded_mix";
    recording.required = required;
    duration.required = required;
  };
  format.addEventListener("change", updateRecorded); updateRecorded();
  form.addEventListener("submit", async event => {
    event.preventDefault();
    feedback.textContent = "Sending your request…";
    const data = Object.fromEntries(new FormData(form).entries());
    data.visuals_enabled = data.visuals_enabled === "1";
    data.rights_confirmed = form.elements.rights_confirmed.checked;
    data.socials = String(data.socials || "").split(/\n+/).map(url => url.trim()).filter(Boolean).map(url => ({ platform: "Social", url }));
    const file = form.elements.logo.files?.[0];
    if (file) {
      if (file.size > 2 * 1024 * 1024 || !["image/png", "image/webp"].includes(file.type)) { feedback.textContent = "Use a transparent PNG or WebP smaller than 2 MB."; return; }
      data.logo_data = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = reject; reader.readAsDataURL(file); });
    }
    delete data.logo; delete data.website;
    try {
      const response = await fetch("/api/public/takeover-application", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Request could not be sent.");
      form.reset(); updateRecorded(); feedback.textContent = result.message || "Request received — the station team will follow up.";
    } catch (error) { feedback.textContent = error.message || "Request could not be sent."; }
  });
})();
