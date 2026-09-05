-- Authorized ALLTHINGS140 alert-repair testers.
-- This is a server-side, time-limited PLUS entitlement only; it is not billing.
-- After expiry, an administrator must run public.finalize_alert_testers() to
-- grant the canonical moderator role. No client can invoke that function.

create table if not exists public.alert_test_accounts (
  email text primary key check (email = lower(trim(email))),
  enrolled_at timestamptz not null default now(),
  duration interval not null default interval '30 days',
  created_by uuid references auth.users(id),
  metadata jsonb not null default '{}'::jsonb
);

alter table public.alert_test_accounts enable row level security;
revoke all on public.alert_test_accounts from anon, authenticated;

insert into public.alert_test_accounts(email, metadata)
values
  ('2019oliverthegreat@gmail.com', '{"purpose":"alert-repair-testing"}'),
  ('adriene.darby@gmail.com', '{"purpose":"alert-repair-testing"}'),
  ('allthings140@gmail.com', '{"purpose":"alert-repair-testing"}'),
  ('dylanstelle615@gmail.com', '{"purpose":"alert-repair-testing"}'),
  ('gonzalezvb88@gmail.com', '{"purpose":"alert-repair-testing"}'),
  ('lereptileofficial@gmail.com', '{"purpose":"alert-repair-testing"}'),
  ('lnr6994@gmail.com', '{"purpose":"alert-repair-testing"}'),
  ('theesoterickingdombusiness@gmail.com', '{"purpose":"alert-repair-testing"}')
on conflict (email) do nothing;

-- Enroll existing accounts immediately; the 30-day clock starts at enrollment.
insert into public.account_classes(user_id, account_class, source, assigned_at, expires_at, metadata)
select u.id, 'plus'::public.account_class, 'manual_test', t.enrolled_at,
       t.enrolled_at + t.duration,
       jsonb_build_object('tester_email', t.email, 'purpose', 'alert-repair-testing')
from auth.users u join public.alert_test_accounts t on lower(u.email)=t.email
on conflict (user_id) do update set account_class=excluded.account_class,
  source='manual_test', assigned_at=excluded.assigned_at, expires_at=excluded.expires_at,
  metadata=excluded.metadata;

-- New signups using an authorized address are enrolled at account creation.
create or replace function public.enroll_alert_test_account()
returns trigger language plpgsql security definer set search_path=public,pg_temp
as $$
begin
  insert into public.account_classes(user_id, account_class, source, assigned_at, expires_at, metadata)
  select new.id, 'plus'::public.account_class, 'manual_test', now(), now()+t.duration,
         jsonb_build_object('tester_email', t.email, 'purpose', 'alert-repair-testing')
  from public.alert_test_accounts t where t.email=lower(new.email)
  on conflict (user_id) do nothing;
  return new;
end;
$$;

drop trigger if exists enroll_alert_test_account on auth.users;
create trigger enroll_alert_test_account after insert on auth.users
for each row execute function public.enroll_alert_test_account();

-- Run as an authenticated administrator after the 30-day test window.
create or replace function public.finalize_alert_testers()
returns integer language plpgsql security definer set search_path=public,pg_temp
as $$
declare n integer;
begin
  if not public.account_is_admin() then raise exception using errcode='42501', message='admin_required'; end if;
  insert into public.user_roles(user_id, role, granted_by)
  select c.user_id, 'moderator', auth.uid()
  from public.account_classes c
  where c.source='manual_test' and c.expires_at is not null and c.expires_at <= now()
  on conflict (user_id, role) do nothing;
  get diagnostics n = row_count;
  return n;
end;
$$;

revoke all on function public.finalize_alert_testers() from public, anon;
grant execute on function public.finalize_alert_testers() to authenticated;
