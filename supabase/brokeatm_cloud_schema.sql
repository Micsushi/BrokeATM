-- budget_hidden_categories uses a surrogate id PK + composite unique(user_id, category_key).
-- The old schema had category_key as the sole PK which breaks multi-user isolation.
-- Run BrokeATM Alembic migrations before this file. This file adds Supabase-only
-- profile/RLS setup and intentionally does not create the app's core tables.

do $$
declare
  missing_tables text[];
begin
  select array_agg(required.table_name)
  into missing_tables
  from unnest(array[
    'accounts',
    'categories',
    'transactions',
    'budget_rules',
    'budget_hidden_categories',
    'recurring_rules',
    'import_batches',
    'app_settings'
  ]) as required(table_name)
  where not exists (
    select 1
    from information_schema.tables
    where table_schema = 'public'
      and table_name = required.table_name
  );

  if missing_tables is not null then
    raise exception 'Run BrokeATM Alembic migrations before Supabase RLS setup. Missing tables: %',
      array_to_string(missing_tables, ', ');
  end if;
end $$;

do $$
declare
  missing_user_id_columns text[];
begin
  select array_agg(required.table_name)
  into missing_user_id_columns
  from unnest(array[
    'accounts',
    'categories',
    'transactions',
    'budget_rules',
    'budget_hidden_categories',
    'recurring_rules',
    'import_batches',
    'app_settings'
  ]) as required(table_name)
  where not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = required.table_name
      and column_name = 'user_id'
  );

  if missing_user_id_columns is not null then
    raise exception 'Run user-scope migration before Supabase RLS setup. Missing user_id columns: %',
      array_to_string(missing_user_id_columns, ', ');
  end if;
end $$;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  username text unique,
  display_name text,
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

drop policy if exists "profiles are owned by user" on public.profiles;
create policy "profiles are owned by user"
on public.profiles
for all
to authenticated
using (auth.uid() = id)
with check (auth.uid() = id);

alter table public.accounts enable row level security;
alter table public.categories enable row level security;
alter table public.transactions enable row level security;
alter table public.budget_rules enable row level security;
alter table public.budget_hidden_categories enable row level security;
alter table public.recurring_rules enable row level security;
alter table public.import_batches enable row level security;
alter table public.app_settings enable row level security;

drop policy if exists "accounts are owned by user" on public.accounts;
create policy "accounts are owned by user" on public.accounts
for all to authenticated using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);

drop policy if exists "categories are owned by user" on public.categories;
create policy "categories are owned by user" on public.categories
for all to authenticated using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);

drop policy if exists "transactions are owned by user" on public.transactions;
create policy "transactions are owned by user" on public.transactions
for all to authenticated using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);

drop policy if exists "budget rules are owned by user" on public.budget_rules;
create policy "budget rules are owned by user" on public.budget_rules
for all to authenticated using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);

drop policy if exists "budget hidden categories are owned by user" on public.budget_hidden_categories;
create policy "budget hidden categories are owned by user" on public.budget_hidden_categories
for all to authenticated using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);

drop policy if exists "recurring rules are owned by user" on public.recurring_rules;
create policy "recurring rules are owned by user" on public.recurring_rules
for all to authenticated using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);

drop policy if exists "import batches are owned by user" on public.import_batches;
create policy "import batches are owned by user" on public.import_batches
for all to authenticated using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);

drop policy if exists "app settings are owned by user" on public.app_settings;
create policy "app settings are owned by user" on public.app_settings
for all to authenticated using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);
