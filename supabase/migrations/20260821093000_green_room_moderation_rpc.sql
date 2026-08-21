-- Server-side moderator operations. Listener clients receive no table grants;
-- these RPCs are executable only by accounts with a protected user_roles row.
create or replace function public.green_room_is_moderator()
returns boolean
language sql stable security definer set search_path = public, pg_temp
as $$ select exists (select 1 from public.user_roles where user_id = auth.uid() and role in ('moderator','admin','staff')); $$;

create or replace function public.green_room_moderator_reports(p_status text default 'pending')
returns setof public.green_room_reports
language plpgsql security definer set search_path = public, pg_temp
as $$
begin
  if not public.green_room_is_moderator() then raise exception using errcode = '42501', message = 'moderator_required'; end if;
  return query select r from public.green_room_reports r where (p_status is null or r.status = p_status) order by r.created_at desc limit 200;
end;
$$;

create or replace function public.green_room_resolve_report(p_report_id uuid, p_status text, p_action text, p_notes text)
returns public.green_room_reports
language plpgsql security definer set search_path = public, pg_temp
as $$
declare row public.green_room_reports;
begin
  if not public.green_room_is_moderator() then raise exception using errcode = '42501', message = 'moderator_required'; end if;
  if p_status not in ('resolved','dismissed') then raise exception using errcode = '22023', message = 'invalid_report_status'; end if;
  update public.green_room_reports set status = p_status, moderator_action = nullif(trim(p_action), ''), moderator_notes = nullif(trim(p_notes), ''), moderator_user_id = auth.uid(), resolved_at = now() where id = p_report_id returning * into row;
  if row.id is null then raise exception using errcode = 'P0002', message = 'report_not_found'; end if;
  insert into public.green_room_moderation_actions(moderator_user_id, target_user_id, message_id, action, reason) values (auth.uid(), row.reported_user_id, row.message_id, case when p_status = 'resolved' then 'resolve' else 'dismiss' end, p_notes);
  return row;
end;
$$;

create or replace function public.green_room_set_account_status(p_user_id uuid, p_status public.account_status, p_reason text default null)
returns public.profiles
language plpgsql security definer set search_path = public, pg_temp
as $$
declare row public.profiles;
begin
  if not public.green_room_is_moderator() then raise exception using errcode = '42501', message = 'moderator_required'; end if;
  update public.profiles set account_status = p_status where id = p_user_id returning * into row;
  if row.id is null then raise exception using errcode = 'P0002', message = 'profile_not_found'; end if;
  insert into public.green_room_moderation_actions(moderator_user_id, target_user_id, action, reason) values (auth.uid(), p_user_id, case p_status when 'banned' then 'ban' when 'suspended' then 'suspend' else 'unban' end, p_reason);
  return row;
end;
$$;

revoke all on function public.green_room_is_moderator() from public, anon, authenticated;
revoke all on function public.green_room_moderator_reports(text) from public, anon, authenticated;
revoke all on function public.green_room_resolve_report(uuid,text,text,text) from public, anon, authenticated;
revoke all on function public.green_room_set_account_status(uuid,public.account_status,text) from public, anon, authenticated;
grant execute on function public.green_room_is_moderator() to authenticated;
grant execute on function public.green_room_moderator_reports(text) to authenticated;
grant execute on function public.green_room_resolve_report(uuid,text,text,text) to authenticated;
grant execute on function public.green_room_set_account_status(uuid,public.account_status,text) to authenticated;
