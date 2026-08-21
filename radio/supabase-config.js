// Public-client configuration only. The publishable key is intentionally safe
// for browser and future Android use when paired with the checked-in RLS rules.
// Never add a Supabase secret/service-role key to this file.
window.AT140SupabaseConfig = Object.freeze({
  url: "https://dtvnlpgtmrbnpecsapsv.supabase.co",
  publishableKey: "sb_publishable_rSf3FiaFsk2zZ37GU0zmzA_2cNQmVJQ",
  avatarBucket: "avatars",
  usernameMin: 3,
  usernameMax: 24,
  usernameCooldownDays: 30,
  maxAvatarBytes: 2 * 1024 * 1024,
  googleEnabled: false,
  soundCloudEnabled: false,
});
