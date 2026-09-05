-- Alert ads are an account entitlement, not a user preference. Retain the
-- legacy table for non-destructive migration history, but remove its RPC
-- authority and return a neutral value from the canonical resolver.
create or replace function public.account_role_state()
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
  )
  select auth.uid(), p.username, auth.jwt()->>'email', coalesce(p.account_status::text, 'active'),
    authority.role, benefit.class,
    case authority.role when 'admin' then 'admin' when 'moderator' then 'moderator' else benefit.class end,
    'default'::text,
    (authority.role = 'user' and benefit.class = 'regular')
  from public.profiles p cross join authority cross join benefit
  where p.id=auth.uid() and auth.uid() is not null;
$$;

-- No client may write an alert preference anymore. Existing rows are inert and
-- can be retained for audit/rollback history without affecting entitlement.
drop function if exists public.set_alert_ads_preference(text);
revoke all on public.alert_ads_preferences from anon, authenticated;
revoke all on function public.account_role_state() from public, anon;
grant execute on function public.account_role_state() to authenticated;
