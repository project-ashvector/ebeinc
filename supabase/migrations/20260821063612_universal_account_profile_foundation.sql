-- ALLTHINGS140 universal account/profile foundation.
-- Supabase Auth owns credentials and the durable auth.users UUID. Public clients
-- receive no privileged database or storage permissions from this migration.

create extension if not exists pgcrypto with schema extensions;

create type public.account_status as enum ('active', 'suspended', 'banned');
create type public.account_role as enum ('moderator', 'admin', 'staff');

create table public.reserved_usernames (
  name_skeleton text primary key,
  reason text not null default 'reserved system identity',
  created_at timestamptz not null default now(),
  constraint reserved_username_skeleton_format
    check (name_skeleton ~ '^[a-z0-9]+$')
);

comment on table public.reserved_usernames is
  'Server-managed username skeletons that listener accounts may not impersonate.';

insert into public.reserved_usernames (name_skeleton) values
  ('allthings140'),
  ('allthings140radio'),
  ('admin'),
  ('administrator'),
  ('moderator'),
  ('mod'),
  ('system'),
  ('support'),
  ('staff');

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  username text,
  avatar_path text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  username_changed_at timestamptz,
  account_status public.account_status not null default 'active',
  terms_version text,
  terms_accepted_at timestamptz,
  constraint profile_username_length
    check (username is null or char_length(username) between 3 and 24),
  constraint profile_username_characters
    check (username is null or username ~ '^[A-Za-z0-9_]+$'),
  constraint profile_avatar_owner_path
    check (avatar_path is null or avatar_path = id::text || '/avatar'),
  constraint profile_terms_acceptance_pair
    check ((terms_version is null) = (terms_accepted_at is null))
);

comment on table public.profiles is
  'One-to-one listener profile keyed by the durable Supabase Auth UUID. Passwords and email remain in Supabase Auth.';
comment on column public.profiles.avatar_path is
  'Storage object path in the public avatars bucket. URL derivation is client/platform independent.';
comment on column public.profiles.account_status is
  'Protected moderation state; never writable by listener clients.';
comment on column public.profiles.terms_version is
  'Protected integration point. Remains null until a later legal/UGC phase publishes a real version.';

create unique index profiles_username_casefold_unique
  on public.profiles (lower(username))
  where username is not null;
create index profiles_account_status_idx on public.profiles (account_status);

create table public.user_roles (
  user_id uuid not null references auth.users(id) on delete cascade,
  role public.account_role not null,
  granted_at timestamptz not null default now(),
  granted_by uuid references auth.users(id) on delete set null,
  primary key (user_id, role)
);

comment on table public.user_roles is
  'Server-managed administrative roles. No anon/authenticated client writes are granted.';

create table public.entitlements (
  user_id uuid primary key references auth.users(id) on delete cascade,
  plan text not null default 'free',
  status text not null default 'inactive',
  ad_free boolean not null default false,
  provider text,
  provider_customer_id text,
  provider_subscription_id text,
  current_period_end timestamptz,
  updated_at timestamptz not null default now(),
  constraint entitlement_status_values
    check (status in ('inactive', 'trialing', 'active', 'past_due', 'canceled', 'expired')),
  constraint entitlement_provider_pair
    check ((provider_customer_id is null and provider_subscription_id is null)
      or provider is not null)
);

comment on table public.entitlements is
  'Future server-controlled subscription truth. Listener clients can read only their own row and can never write it.';

create table public.account_deletion_requests (
  id uuid primary key default extensions.gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  requested_at timestamptz not null default now(),
  status text not null default 'pending',
  processed_at timestamptz,
  constraint deletion_request_status_values
    check (status in ('pending', 'processing', 'completed', 'rejected'))
);

create unique index account_deletion_one_open_request
  on public.account_deletion_requests (user_id)
  where status in ('pending', 'processing');

comment on table public.account_deletion_requests is
  'Deletion queue only. A secure server/Edge Function must remove Storage objects, related data, and auth.users.';

create or replace function public.username_skeleton(candidate text)
returns text
language sql
immutable
strict
set search_path = ''
as $$
  select regexp_replace(lower(trim(candidate)), '[^a-z0-9]', '', 'g');
$$;

create or replace function public.enforce_profile_write()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  normalized text;
begin
  if new.username is not null then
    normalized := trim(new.username);

    if char_length(normalized) < 3 or char_length(normalized) > 24 then
      raise exception using errcode = '22023', message = 'username_length';
    end if;
    if normalized !~ '^[A-Za-z0-9_]+$' then
      raise exception using errcode = '22023', message = 'username_characters';
    end if;
    if exists (
      select 1
      from public.reserved_usernames r
      where r.name_skeleton = public.username_skeleton(normalized)
    ) then
      raise exception using errcode = '22023', message = 'username_reserved';
    end if;

    new.username := normalized;
  end if;

  if tg_op = 'UPDATE' and new.username is distinct from old.username then
    if old.username is not null
      and old.username_changed_at is not null
      and old.username_changed_at > now() - interval '30 days' then
      raise exception using errcode = '22023', message = 'username_cooldown';
    end if;
    new.username_changed_at := now();
  elsif tg_op = 'INSERT' and new.username is not null then
    new.username_changed_at := now();
  end if;

  new.updated_at := now();
  return new;
end;
$$;

create trigger profiles_enforce_write
before insert or update on public.profiles
for each row execute function public.enforce_profile_write();

create or replace function public.bootstrap_auth_profile()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  insert into public.profiles (id)
  values (new.id)
  on conflict (id) do nothing;

  insert into public.entitlements (user_id)
  values (new.id)
  on conflict (user_id) do nothing;

  return new;
end;
$$;

create trigger auth_user_profile_bootstrap
after insert on auth.users
for each row execute function public.bootstrap_auth_profile();

create or replace function public.request_my_account_deletion()
returns public.account_deletion_requests
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  request_row public.account_deletion_requests;
begin
  if auth.uid() is null then
    raise exception using errcode = '42501', message = 'authentication_required';
  end if;

  insert into public.account_deletion_requests (user_id)
  values (auth.uid())
  on conflict (user_id) where status in ('pending', 'processing')
  do update set requested_at = public.account_deletion_requests.requested_at
  returning * into request_row;

  return request_row;
end;
$$;

alter table public.reserved_usernames enable row level security;
alter table public.profiles enable row level security;
alter table public.user_roles enable row level security;
alter table public.entitlements enable row level security;
alter table public.account_deletion_requests enable row level security;

create policy profiles_public_read
on public.profiles
for select
to anon, authenticated
using (username is not null);

create policy profiles_owner_read
on public.profiles
for select
to authenticated
using (auth.uid() = id);

create policy profiles_owner_update
on public.profiles
for update
to authenticated
using (auth.uid() = id)
with check (auth.uid() = id);

create policy entitlements_owner_read
on public.entitlements
for select
to authenticated
using (auth.uid() = user_id);

create policy deletion_requests_owner_read
on public.account_deletion_requests
for select
to authenticated
using (auth.uid() = user_id);

revoke all on table public.reserved_usernames from anon, authenticated;
revoke all on table public.profiles from anon, authenticated;
revoke all on table public.user_roles from anon, authenticated;
revoke all on table public.entitlements from anon, authenticated;
revoke all on table public.account_deletion_requests from anon, authenticated;

grant select (id, username, avatar_path, created_at, updated_at, account_status)
  on table public.profiles to anon, authenticated;
grant select (username_changed_at) on table public.profiles to authenticated;
grant update (username, avatar_path)
  on table public.profiles to authenticated;
grant select on table public.entitlements to authenticated;
grant select on table public.account_deletion_requests to authenticated;

revoke all on function public.username_skeleton(text) from public, anon, authenticated;
revoke all on function public.enforce_profile_write() from public, anon, authenticated;
revoke all on function public.bootstrap_auth_profile() from public, anon, authenticated;
revoke all on function public.request_my_account_deletion() from public, anon;
grant execute on function public.request_my_account_deletion() to authenticated;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'avatars',
  'avatars',
  true,
  2097152,
  array['image/jpeg', 'image/png', 'image/webp']
)
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

create policy avatar_public_read
on storage.objects
for select
to anon, authenticated
using (bucket_id = 'avatars');

create policy avatar_owner_insert
on storage.objects
for insert
to authenticated
with check (
  bucket_id = 'avatars'
  and name = auth.uid()::text || '/avatar'
);

create policy avatar_owner_update
on storage.objects
for update
to authenticated
using (
  bucket_id = 'avatars'
  and name = auth.uid()::text || '/avatar'
)
with check (
  bucket_id = 'avatars'
  and name = auth.uid()::text || '/avatar'
);

create policy avatar_owner_delete
on storage.objects
for delete
to authenticated
using (
  bucket_id = 'avatars'
  and name = auth.uid()::text || '/avatar'
);
