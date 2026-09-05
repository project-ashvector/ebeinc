-- ALLTHINGS140 role-aware account administration.
-- public.user_roles remains the sole role authority; normal users have no row.

alter table public.green_room_moderation_actions
  drop constraint if exists green_room_action_values;
alter table public.green_room_moderation_actions
  add constraint green_room_action_values check (action in (
    'delete','mute','suspend','ban','unban','resolve','dismiss',
    'moderator_assign','moderator_remove'
  ));

create or replace function public.green_room_resolve_report(p_report_id uuid, p_status text, p_action text, p_notes text)
returns public.green_room_reports language plpgsql security definer set search_path = public, pg_temp
as $$
declare row public.green_room_reports; audit_action text;
begin
  if not public.green_room_is_moderator() then raise exception using errcode='42501', message='moderator_required'; end if;
  if p_status not in ('resolved','dismissed') then raise exception using errcode='22023', message='invalid_report_status'; end if;
  update public.green_room_reports set status=p_status, moderator_action=nullif(trim(p_action),''),
    moderator_notes=nullif(trim(p_notes),''), moderator_user_id=auth.uid(), resolved_at=now()
    where id=p_report_id returning * into row;
  if row.id is null then raise exception using errcode='P0002', message='report_not_found'; end if;
  audit_action := case when upper(coalesce(p_action,''))='MESSAGE_DELETE' then 'delete'
    when p_status='resolved' then 'resolve' else 'dismiss' end;
  insert into public.green_room_moderation_actions(moderator_user_id,target_user_id,message_id,action,reason)
    values(auth.uid(),row.reported_user_id,row.message_id,audit_action,p_notes);
  return row;
end;
$$;

create or replace function public.account_role_state()
returns table (user_id uuid, username text, email text, account_status text, role text)
language sql stable security definer set search_path = public, auth, pg_temp
as $$
  select auth.uid(), p.username, auth.jwt()->>'email', coalesce(p.account_status::text, 'active'),
    coalesce((select case
      when bool_or(r.role = 'admin') then 'admin'
      when bool_or(r.role in ('moderator','staff')) then 'moderator'
      else 'user' end
      from public.user_roles r where r.user_id = auth.uid()), 'user')
  from public.profiles p where p.id = auth.uid() and auth.uid() is not null;
$$;

create or replace function public.account_is_admin()
returns boolean language sql stable security definer set search_path = public, pg_temp
as $$ select auth.uid() is not null and exists (
  select 1 from public.user_roles where user_id = auth.uid() and role = 'admin'
); $$;

create or replace function public.moderator_recent_actions(p_limit integer default 50)
returns table (id uuid, actor_user_id uuid, actor_username text, target_user_id uuid,
  target_username text, message_id text, action text, reason text, created_at timestamptz)
language plpgsql stable security definer set search_path = public, pg_temp
as $$
begin
  if not public.green_room_is_moderator() then
    raise exception using errcode = '42501', message = 'moderator_required';
  end if;
  return query select a.id, a.moderator_user_id, actor.username, a.target_user_id,
    target.username, a.message_id, a.action, a.reason, a.created_at
  from public.green_room_moderation_actions a
  left join public.profiles actor on actor.id = a.moderator_user_id
  left join public.profiles target on target.id = a.target_user_id
  order by a.created_at desc limit greatest(1, least(coalesce(p_limit, 50), 200));
end;
$$;

create or replace function public.admin_lookup_user(p_query text)
returns table (user_id uuid, username text, email text, account_status text, role text,
  avatar_path text, created_at timestamptz)
language plpgsql stable security definer set search_path = public, auth, pg_temp
as $$
declare q text := trim(coalesce(p_query, ''));
begin
  if not public.account_is_admin() then
    raise exception using errcode = '42501', message = 'admin_required';
  end if;
  if char_length(q) < 2 then
    raise exception using errcode = '22023', message = 'lookup_query_too_short';
  end if;
  return query select u.id, p.username, u.email, p.account_status::text,
    coalesce(case
      when bool_or(r.role = 'admin') then 'admin'
      when bool_or(r.role in ('moderator','staff')) then 'moderator'
      else 'user' end, 'user'), p.avatar_path, u.created_at
  from auth.users u join public.profiles p on p.id = u.id
  left join public.user_roles r on r.user_id = u.id
  where u.id::text = q or lower(coalesce(u.email, '')) like '%' || lower(q) || '%'
    or lower(coalesce(p.username, '')) like '%' || lower(q) || '%'
  group by u.id, p.username, u.email, p.account_status, p.avatar_path, u.created_at
  order by p.username nulls last, u.created_at desc limit 50;
end;
$$;

create or replace function public.admin_assign_moderator(p_user_id uuid, p_reason text default null)
returns public.user_roles language plpgsql security definer set search_path = public, pg_temp
as $$
declare row public.user_roles;
begin
  if not public.account_is_admin() then raise exception using errcode='42501', message='admin_required'; end if;
  if p_user_id is null or not exists (select 1 from public.profiles where id=p_user_id)
    then raise exception using errcode='P0002', message='user_not_found'; end if;
  insert into public.user_roles(user_id, role, granted_by) values(p_user_id, 'moderator', auth.uid())
  on conflict (user_id, role) do update set granted_by=auth.uid(), granted_at=now() returning * into row;
  insert into public.green_room_moderation_actions(moderator_user_id,target_user_id,action,reason)
    values(auth.uid(),p_user_id,'moderator_assign',nullif(trim(p_reason),''));
  return row;
end;
$$;

create or replace function public.admin_remove_moderator(p_user_id uuid, p_reason text default null)
returns boolean language plpgsql security definer set search_path = public, pg_temp
as $$
declare removed boolean;
begin
  if not public.account_is_admin() then raise exception using errcode='42501', message='admin_required'; end if;
  if exists(select 1 from public.user_roles where user_id=p_user_id and role='admin')
    then raise exception using errcode='42501', message='admin_role_protected'; end if;
  delete from public.user_roles where user_id=p_user_id and role in ('moderator','staff');
  removed := found;
  insert into public.green_room_moderation_actions(moderator_user_id,target_user_id,action,reason)
    values(auth.uid(),p_user_id,'moderator_remove',nullif(trim(p_reason),''));
  return removed;
end;
$$;

create or replace function public.green_room_set_account_status(p_user_id uuid, p_status public.account_status, p_reason text default null)
returns public.profiles language plpgsql security definer set search_path = public, pg_temp
as $$
declare row public.profiles;
begin
  if not public.green_room_is_moderator() then raise exception using errcode='42501', message='moderator_required'; end if;
  if p_user_id = auth.uid() then raise exception using errcode='42501', message='self_status_change_protected'; end if;
  if exists(select 1 from public.user_roles where user_id=p_user_id and role='admin')
    then raise exception using errcode='42501', message='admin_account_protected'; end if;
  update public.profiles set account_status=p_status where id=p_user_id returning * into row;
  if row.id is null then raise exception using errcode='P0002', message='profile_not_found'; end if;
  insert into public.green_room_moderation_actions(moderator_user_id,target_user_id,action,reason)
    values(auth.uid(),p_user_id,case p_status when 'banned' then 'ban' when 'suspended' then 'suspend' else 'unban' end,nullif(trim(p_reason),''));
  return row;
end;
$$;

create or replace function public.green_room_record_message_delete(p_message_id text, p_target_user_id uuid, p_reason text default null)
returns boolean language plpgsql security definer set search_path = public, pg_temp
as $$
begin
  if not public.green_room_is_moderator() then raise exception using errcode='42501', message='moderator_required'; end if;
  if length(trim(coalesce(p_message_id,''))) not between 1 and 120
    then raise exception using errcode='22023', message='message_id_invalid'; end if;
  insert into public.green_room_moderation_actions(moderator_user_id,target_user_id,message_id,action,reason)
    values(auth.uid(),p_target_user_id,trim(p_message_id),'delete',nullif(trim(p_reason),''));
  return true;
end;
$$;

revoke all on function public.account_role_state() from public, anon;
revoke all on function public.account_is_admin() from public, anon, authenticated;
revoke all on function public.moderator_recent_actions(integer) from public, anon;
revoke all on function public.admin_lookup_user(text) from public, anon;
revoke all on function public.admin_assign_moderator(uuid,text) from public, anon;
revoke all on function public.admin_remove_moderator(uuid,text) from public, anon;
revoke all on function public.green_room_record_message_delete(text,uuid,text) from public, anon;
grant execute on function public.account_role_state() to authenticated;
grant execute on function public.moderator_recent_actions(integer) to authenticated;
grant execute on function public.admin_lookup_user(text) to authenticated;
grant execute on function public.admin_assign_moderator(uuid,text) to authenticated;
grant execute on function public.admin_remove_moderator(uuid,text) to authenticated;
grant execute on function public.green_room_record_message_delete(text,uuid,text) to authenticated;

-- One-time bootstrap: email is used only for this authorized account lookup.
-- Runtime authorization always resolves through auth.users.id -> user_roles.
insert into public.user_roles(user_id, role, granted_by)
select id, 'admin', id from auth.users where lower(email)=lower('allthings140@gmail.com')
on conflict (user_id, role) do nothing;
