-- Provider-verified PLUS subscriptions. Clients have no write authority.
create extension if not exists pgcrypto with schema extensions;

create table if not exists public.billing_subscriptions (
  provider text not null check (provider in ('stripe','google_play')),
  provider_subscription_id text not null,
  user_id uuid not null references auth.users(id) on delete cascade,
  provider_customer_id text,
  product_id text not null,
  status text not null,
  current_period_end timestamptz,
  cancel_at_period_end boolean not null default false,
  updated_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  primary key (provider, provider_subscription_id)
);
alter table public.billing_subscriptions enable row level security;
revoke all on public.billing_subscriptions from anon, authenticated;
drop policy if exists billing_subscription_owner_read on public.billing_subscriptions;
create policy billing_subscription_owner_read on public.billing_subscriptions for select to authenticated
  using (user_id=auth.uid());
grant select on public.billing_subscriptions to authenticated;

create or replace function public.billing_apply_entitlement(
  p_secret text, p_provider text, p_subscription_id text, p_user_id uuid,
  p_customer_id text, p_product_id text, p_status text,
  p_period_end timestamptz default null, p_cancel_at_period_end boolean default false,
  p_metadata jsonb default '{}'::jsonb)
returns void language plpgsql security definer set search_path=public,extensions,pg_temp as $$
declare active boolean := lower(p_status) in ('active','trialing','past_due','in_grace_period');
begin
  if encode(digest(coalesce(p_secret,''),'sha256'),'hex') <> '34504aa33b97029d14c03f44bf98530f55e69a9f30b879fcb9525b92c5762aba'
    then raise exception using errcode='42501',message='billing_authority_required'; end if;
  if p_provider not in ('stripe','google_play') or p_subscription_id='' or p_user_id is null
    then raise exception using errcode='22023',message='invalid_billing_record'; end if;
  insert into public.billing_subscriptions(provider,provider_subscription_id,user_id,provider_customer_id,
    product_id,status,current_period_end,cancel_at_period_end,updated_at,metadata)
  values(p_provider,p_subscription_id,p_user_id,nullif(p_customer_id,''),p_product_id,lower(p_status),
    p_period_end,p_cancel_at_period_end,now(),coalesce(p_metadata,'{}'::jsonb))
  on conflict(provider,provider_subscription_id) do update set user_id=excluded.user_id,
    provider_customer_id=excluded.provider_customer_id,product_id=excluded.product_id,status=excluded.status,
    current_period_end=excluded.current_period_end,cancel_at_period_end=excluded.cancel_at_period_end,
    updated_at=now(),metadata=excluded.metadata;
  if active then
    insert into public.account_classes(user_id,account_class,source,assigned_at,expires_at,metadata)
    values(p_user_id,'plus','subscription',now(),p_period_end,
      jsonb_build_object('provider',p_provider,'subscription_id',p_subscription_id))
    on conflict(user_id) do update set account_class='plus',source='subscription',assigned_by=null,
      assigned_at=now(),expires_at=excluded.expires_at,metadata=excluded.metadata;
  elsif not exists (
    select 1 from public.billing_subscriptions b
    where b.user_id=p_user_id
      and not (b.provider=p_provider and b.provider_subscription_id=p_subscription_id)
      and lower(b.status) in ('active','trialing','past_due','in_grace_period')
  ) then
    update public.account_classes set account_class='regular',source='default',assigned_by=null,
      assigned_at=now(),expires_at=null,metadata='{}'::jsonb
    where user_id=p_user_id and source='subscription'
      and metadata->>'provider'=p_provider and metadata->>'subscription_id'=p_subscription_id;
  end if;
end; $$;
revoke all on function public.billing_apply_entitlement(text,text,text,uuid,text,text,text,timestamptz,boolean,jsonb) from public;
grant execute on function public.billing_apply_entitlement(text,text,text,uuid,text,text,text,timestamptz,boolean,jsonb) to anon,authenticated;
