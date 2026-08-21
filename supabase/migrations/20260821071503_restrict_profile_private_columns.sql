-- The cooldown timestamp is enforcement state, not part of the public profile.
-- The database trigger remains authoritative; clients only need to know that a
-- completed username is subject to the documented 30-day policy.
revoke select (username_changed_at) on table public.profiles from authenticated;
