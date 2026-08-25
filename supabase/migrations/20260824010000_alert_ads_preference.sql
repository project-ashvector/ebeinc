-- Per-user station-alert preference. Account class and staff role remain the
-- protected authority; this preference can only opt eligible accounts back in.

create table if not exists public.alert_ads_preferences (
  user_id uuid primary key references auth.users(id) on delete cascade,
  preference text not null default 'default' check (preference in ('default','on','off')),
  updated_at timestamptz not null default now()
);

alter table public.alert_ads_preferences enable row level security;
revoke all on public.alert_ads_preferences from anon, authenticated;

drop function if exists public.account_role_state();

create function public.account_role_state()
returns table (user_id uuid, username text, email text, account_status text, role text,
  account_class text, account_type text, alert_ads_preference text, alert_ads_enabled boolean)
language sql stable security definer set search_path = public, auth, pg_temp
as $$
  with authority as (
    select coalesce(case
      when bool_or(r.role = 'admin') then 'admin'
      when bool_or(r.role in ('moderator','staff')) then 'moderator'
      else 'user' end, 'user') role
    from public.user_roles r where r.user_id = auth.uid()
  ), benefit as (
    select coalesce((select c.account_class::text from public.account_classes c
      where c.user_id=auth.uid() and (c.expires_at is null or c.expires_at > now())), 'regular') class
  ), preference as (
    select coalesce((select a.preference from public.alert_ads_preferences a
      where a.user_id=auth.uid()), 'default') value
  )
  select auth.uid(), p.username, auth.jwt()->>'email', coalesce(p.account_status::text, 'active'),
    authority.role, benefit.class,
    case authority.role when 'admin' then 'admin' when 'moderator' then 'moderator' else benefit.class end,
    preference.value,
    case
      when authority.role='user' and benefit.class='regular' then true
      when preference.value='on' then true
      else false
    end
  from public.profiles p cross join authority cross join benefit cross join preference
  where p.id=auth.uid() and auth.uid() is not null;
$$;

create or replace function public.set_alert_ads_preference(p_preference text)
returns table (alert_ads_preference text, alert_ads_enabled boolean)
language plpgsql security definer set search_path=public,auth,pg_temp
as $$
declare
  requested text := lower(trim(coalesce(p_preference,'')));
  security_role text;
  benefit_class text;
begin
  if auth.uid() is null then
    raise exception using errcode='42501', message='authentication_required';
  end if;
  if requested not in ('default','on','off') then
    raise exception using errcode='22023', message='invalid_alert_ads_preference';
  end if;

  select coalesce(case
      when bool_or(r.role='admin') then 'admin'
      when bool_or(r.role in ('moderator','staff')) then 'moderator'
      else 'user' end,'user')
    into security_role from public.user_roles r where r.user_id=auth.uid();
  select coalesce((select c.account_class::text from public.account_classes c
      where c.user_id=auth.uid() and (c.expires_at is null or c.expires_at>now())), 'regular')
    into benefit_class;

  if security_role='user' and benefit_class='regular' and requested <> 'on' then
    raise exception using errcode='42501', message='regular_alert_ads_locked_on';
  end if;

  insert into public.alert_ads_preferences(user_id,preference,updated_at)
    values(auth.uid(),requested,now())
  on conflict(user_id) do update set preference=excluded.preference,updated_at=excluded.updated_at;

  return query select requested,
    case when security_role='user' and benefit_class='regular' then true
      when requested='on' then true else false end;
end;
$$;

revoke all on function public.account_role_state() from public,anon;
revoke all on function public.set_alert_ads_preference(text) from public,anon;
grant execute on function public.account_role_state() to authenticated;
grant execute on function public.set_alert_ads_preference(text) to authenticated;

comment on table public.alert_ads_preferences is
  'Protected own-account station-alert opt-in preference. Never grants ad-free eligibility.';
comment on function public.set_alert_ads_preference(text) is
  'Writes only auth.uid preference and keeps Regular accounts effectively locked on.';
