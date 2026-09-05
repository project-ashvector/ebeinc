-- ALLTHINGS140 permanent account classes and derived alert entitlement.
-- Security authority remains public.user_roles; benefits never grant staff access.

do $$ begin
  create type public.account_class as enum ('regular','plus','resident','partner_sponsor');
exception when duplicate_object then null; end $$;

create table if not exists public.account_classes (
  user_id uuid primary key references auth.users(id) on delete cascade,
  account_class public.account_class not null default 'regular',
  source text not null default 'default' check (source in ('default','manual_test','admin','subscription','resident','partner')),
  assigned_by uuid references auth.users(id),
  assigned_at timestamptz not null default now(),
  expires_at timestamptz,
  metadata jsonb not null default '{}'::jsonb
);

alter table public.account_classes enable row level security;
revoke all on public.account_classes from anon, authenticated;

alter table public.green_room_moderation_actions drop constraint if exists green_room_action_values;
alter table public.green_room_moderation_actions add constraint green_room_action_values check (action in (
  'delete','mute','suspend','ban','unban','resolve','dismiss',
  'moderator_assign','moderator_remove','account_class_assign'
));

drop function if exists public.account_role_state();

create or replace function public.account_role_state()
returns table (user_id uuid, username text, email text, account_status text, role text,
  account_class text, account_type text, alert_ads_enabled boolean)
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
    authority.role = 'user' and benefit.class = 'regular'
  from public.profiles p cross join authority cross join benefit
  where p.id = auth.uid() and auth.uid() is not null;
$$;

drop function if exists public.admin_lookup_user(text);

create function public.admin_lookup_user(p_query text)
returns table (user_id uuid, username text, email text, account_status text, role text,
  account_class text, account_type text, alert_ads_enabled boolean,
  account_class_source text, avatar_path text, created_at timestamptz)
language plpgsql stable security definer set search_path = public, auth, pg_temp
as $$
declare q text := trim(coalesce(p_query, ''));
begin
  if not public.account_is_admin() then raise exception using errcode='42501', message='admin_required'; end if;
  if char_length(q) < 2 then raise exception using errcode='22023', message='lookup_query_too_short'; end if;
  return query
  with users as (
    select u.id, p.username, u.email, p.account_status::text status, p.avatar_path, u.created_at,
      coalesce(case when bool_or(r.role='admin') then 'admin'
        when bool_or(r.role in ('moderator','staff')) then 'moderator' else 'user' end,'user') security_role
    from auth.users u join public.profiles p on p.id=u.id left join public.user_roles r on r.user_id=u.id
    where u.id::text=q or lower(coalesce(u.email,'')) like '%'||lower(q)||'%'
      or lower(coalesce(p.username,'')) like '%'||lower(q)||'%'
    group by u.id,p.username,u.email,p.account_status,p.avatar_path,u.created_at
  )
  select u.id,u.username,u.email,u.status,u.security_role,
    coalesce(c.account_class::text,'regular'),
    case u.security_role when 'admin' then 'admin' when 'moderator' then 'moderator'
      else coalesce(c.account_class::text,'regular') end,
    u.security_role='user' and coalesce(c.account_class::text,'regular')='regular',
    coalesce(c.source,'default'),u.avatar_path,u.created_at
  from users u left join public.account_classes c on c.user_id=u.id
    and (c.expires_at is null or c.expires_at>now())
  order by u.username nulls last,u.created_at desc limit 50;
end;
$$;

create or replace function public.admin_set_account_class(
  p_user_id uuid, p_account_class public.account_class, p_source text default 'admin', p_reason text default null)
returns public.account_classes language plpgsql security definer set search_path=public,pg_temp
as $$
declare row public.account_classes; safe_source text;
begin
  if not public.account_is_admin() then raise exception using errcode='42501',message='admin_required'; end if;
  if p_user_id is null or not exists(select 1 from public.profiles where id=p_user_id)
    then raise exception using errcode='P0002',message='user_not_found'; end if;
  safe_source := case when p_account_class='plus' and p_source='manual_test' then 'manual_test'
    when p_account_class='resident' then 'resident' when p_account_class='partner_sponsor' then 'partner'
    else 'admin' end;
  insert into public.account_classes(user_id,account_class,source,assigned_by,assigned_at,expires_at,metadata)
    values(p_user_id,p_account_class,safe_source,auth.uid(),now(),null,
      jsonb_build_object('reason',nullif(trim(coalesce(p_reason,'')),'')))
  on conflict(user_id) do update set account_class=excluded.account_class,source=excluded.source,
    assigned_by=auth.uid(),assigned_at=now(),expires_at=null,metadata=excluded.metadata returning * into row;
  insert into public.green_room_moderation_actions(moderator_user_id,target_user_id,action,reason)
    values(auth.uid(),p_user_id,'account_class_assign',concat(p_account_class::text,': ',nullif(trim(coalesce(p_reason,'')),'')));
  return row;
end;
$$;

revoke all on function public.account_role_state() from public,anon;
revoke all on function public.admin_lookup_user(text) from public,anon;
revoke all on function public.admin_set_account_class(uuid,public.account_class,text,text) from public,anon;
grant execute on function public.account_role_state() to authenticated;
grant execute on function public.admin_lookup_user(text) to authenticated;
grant execute on function public.admin_set_account_class(uuid,public.account_class,text,text) to authenticated;
