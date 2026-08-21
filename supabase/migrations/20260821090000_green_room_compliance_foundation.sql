-- Green Room compliance foundation.  The Durable Object remains the public
-- WebSocket transport; these tables hold account-scoped consent, blocks, and
-- durable moderation evidence outside the five-minute public message window.

create table public.green_room_terms_acceptances (
  user_id uuid not null references auth.users(id) on delete cascade,
  terms_version text not null,
  accepted_at timestamptz not null default now(),
  primary key (user_id, terms_version),
  constraint green_room_terms_version_format check (terms_version ~ '^[a-z0-9-]{8,80}$')
);

create table public.green_room_blocks (
  blocker_user_id uuid not null references auth.users(id) on delete cascade,
  blocked_user_id uuid not null references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (blocker_user_id, blocked_user_id),
  constraint green_room_block_not_self check (blocker_user_id <> blocked_user_id)
);

create table public.green_room_reports (
  id uuid primary key default extensions.gen_random_uuid(),
  reporter_user_id uuid not null references auth.users(id) on delete cascade,
  reported_user_id uuid references auth.users(id) on delete set null,
  message_id text not null,
  reason text not null,
  reporter_note text,
  message_snapshot jsonb not null,
  created_at timestamptz not null default now(),
  status text not null default 'pending',
  moderator_action text,
  moderator_notes text,
  moderator_user_id uuid references auth.users(id) on delete set null,
  resolved_at timestamptz,
  constraint green_room_report_reason check (reason in ('harassment','hate','sexual','threat','spam','scam','privacy','copyright','other')),
  constraint green_room_report_status check (status in ('pending','reviewing','resolved','dismissed')),
  constraint green_room_report_note_length check (reporter_note is null or char_length(reporter_note) <= 500),
  constraint green_room_report_snapshot_object check (jsonb_typeof(message_snapshot) = 'object')
);
create index green_room_reports_pending_idx on public.green_room_reports(status, created_at desc);
create index green_room_reports_message_idx on public.green_room_reports(message_id, created_at desc);

create table public.green_room_moderation_actions (
  id uuid primary key default extensions.gen_random_uuid(),
  moderator_user_id uuid not null references auth.users(id) on delete restrict,
  target_user_id uuid references auth.users(id) on delete set null,
  message_id text,
  action text not null,
  reason text,
  created_at timestamptz not null default now(),
  constraint green_room_action_values check (action in ('delete','mute','suspend','ban','unban','resolve','dismiss'))
);

alter table public.green_room_terms_acceptances enable row level security;
alter table public.green_room_blocks enable row level security;
alter table public.green_room_reports enable row level security;
alter table public.green_room_moderation_actions enable row level security;

create policy green_room_terms_owner_read on public.green_room_terms_acceptances
  for select to authenticated using (auth.uid() = user_id);
create policy green_room_blocks_owner_read on public.green_room_blocks
  for select to authenticated using (auth.uid() = blocker_user_id);
create policy green_room_blocks_owner_insert on public.green_room_blocks
  for insert to authenticated with check (auth.uid() = blocker_user_id);
create policy green_room_blocks_owner_delete on public.green_room_blocks
  for delete to authenticated using (auth.uid() = blocker_user_id);

revoke all on table public.green_room_terms_acceptances from anon, authenticated;
revoke all on table public.green_room_blocks from anon, authenticated;
revoke all on table public.green_room_reports from anon, authenticated;
revoke all on table public.green_room_moderation_actions from anon, authenticated;
grant select on table public.green_room_terms_acceptances to authenticated;
grant select, insert, delete on table public.green_room_blocks to authenticated;

create or replace function public.green_room_current_policy()
returns table (terms_version text, public_ttl_seconds integer)
language sql immutable security invoker
set search_path = public
as $$ select 'green-room-2026-08-21-v1'::text, 300::integer $$;

create or replace function public.accept_green_room_terms(p_terms_version text)
returns public.green_room_terms_acceptances
language plpgsql security definer
set search_path = public, pg_temp
as $$
declare row public.green_room_terms_acceptances;
begin
  if auth.uid() is null then raise exception using errcode = '42501', message = 'authentication_required'; end if;
  if p_terms_version is distinct from 'green-room-2026-08-21-v1' then
    raise exception using errcode = '22023', message = 'terms_version_required';
  end if;
  insert into public.green_room_terms_acceptances(user_id, terms_version)
  values (auth.uid(), p_terms_version)
  on conflict (user_id, terms_version) do update set accepted_at = public.green_room_terms_acceptances.accepted_at
  returning * into row;
  return row;
end;
$$;

create or replace function public.green_room_can_post()
returns table (allowed boolean, reason text, terms_version text)
language plpgsql security definer
set search_path = public, pg_temp
as $$
declare status_value public.account_status; current_version text := 'green-room-2026-08-21-v1';
begin
  if auth.uid() is null then return query select false, 'sign_in_required', current_version; return; end if;
  select p.account_status into status_value from public.profiles p where p.id = auth.uid();
  if status_value is null then return query select false, 'profile_required', current_version; return; end if;
  if status_value = 'banned' then return query select false, 'account_banned', current_version; return; end if;
  if status_value = 'suspended' then return query select false, 'account_suspended', current_version; return; end if;
  if not exists (select 1 from public.green_room_terms_acceptances a where a.user_id = auth.uid() and a.terms_version = current_version)
    then return query select false, 'terms_acceptance_required', current_version; return; end if;
  return query select true, 'allowed', current_version;
end;
$$;

create or replace function public.submit_green_room_report(
  p_reported_user_id uuid,
  p_message_id text,
  p_reason text,
  p_reporter_note text,
  p_message_snapshot jsonb
)
returns public.green_room_reports
language plpgsql security definer
set search_path = public, pg_temp
as $$
declare row public.green_room_reports;
begin
  if auth.uid() is null then raise exception using errcode = '42501', message = 'authentication_required'; end if;
  if length(trim(coalesce(p_message_id, ''))) not between 1 and 120 then raise exception using errcode = '22023', message = 'message_id_invalid'; end if;
  if p_reason not in ('harassment','hate','sexual','threat','spam','scam','privacy','copyright','other') then raise exception using errcode = '22023', message = 'report_reason_invalid'; end if;
  if p_message_snapshot is null or jsonb_typeof(p_message_snapshot) <> 'object' then raise exception using errcode = '22023', message = 'message_snapshot_required'; end if;
  insert into public.green_room_reports(reporter_user_id, reported_user_id, message_id, reason, reporter_note, message_snapshot)
  values (auth.uid(), p_reported_user_id, trim(p_message_id), p_reason, nullif(trim(p_reporter_note), ''), p_message_snapshot)
  returning * into row;
  return row;
end;
$$;

revoke all on function public.green_room_current_policy() from public, anon, authenticated;
revoke all on function public.accept_green_room_terms(text) from public, anon;
revoke all on function public.green_room_can_post() from public, anon;
revoke all on function public.submit_green_room_report(uuid,text,text,text,jsonb) from public, anon;
grant execute on function public.green_room_current_policy() to anon, authenticated;
grant execute on function public.accept_green_room_terms(text) to authenticated;
grant execute on function public.green_room_can_post() to anon, authenticated;
grant execute on function public.submit_green_room_report(uuid,text,text,text,jsonb) to authenticated;
