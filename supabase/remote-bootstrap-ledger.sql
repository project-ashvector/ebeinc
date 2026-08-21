-- One-time hosted-project bootstrap used because this pre-existing project had
-- no Supabase CLI migration ledger and CLI authentication was unavailable.
-- The table shapes match Supabase CLI 2.115.0 local initialization.

create schema if not exists supabase_migrations;

create table if not exists supabase_migrations.schema_migrations (
  version text primary key,
  statements text[],
  name text
);

create table if not exists supabase_migrations.seed_files (
  path text primary key,
  hash text not null
);

insert into supabase_migrations.schema_migrations (version, name, statements)
values (
  '20260821063612',
  'universal_account_profile_foundation',
  array[]::text[]
)
on conflict (version) do update set name = excluded.name;
