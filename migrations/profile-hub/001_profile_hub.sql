-- Run in the Supabase project used for Auth, not a separate crawler database.
begin;
-- Enforce the same closed document shapes used by the API, including direct RPC calls.
create or replace function public.profile_hub_integer(v jsonb, lo integer, hi integer)
returns boolean language sql immutable set search_path = '' as $$
  select coalesce(case when jsonb_typeof(v) = 'number' and v::text ~ '^[0-9]+$'
    then v::text::numeric between lo and hi else false end, false);
$$;
create or replace function public.profile_hub_payload_valid(k text, p jsonb)
returns boolean language plpgsql immutable set search_path = '' as $$
declare
  v jsonb;
  key text;
  keys text[];
begin
  if p is null then return true; end if;
  if jsonb_typeof(p) <> 'object' or octet_length(p::text) > 12000 then return false; end if;
  if k = 'preferences' then
    keys := array['hotel_stars','duration_days','shopping','prefer_lower_listed_price','levels'];
    if not p ?& keys or p - keys <> '{}'::jsonb then return false; end if;
    if not (p->'hotel_stars' = 'null'::jsonb or public.profile_hub_integer(p->'hotel_stars',1,5))
       or not (p->'duration_days' = 'null'::jsonb or public.profile_hub_integer(p->'duration_days',1,90))
       or jsonb_typeof(p->'shopping') <> 'string' or p->>'shopping' not in ('any','few')
       or jsonb_typeof(p->'prefer_lower_listed_price') <> 'boolean' then return false; end if;
    v := p->'levels'; keys := array['cost','comfort','pace','culture'];
    if jsonb_typeof(v) <> 'object' or not v ?& keys or v - keys <> '{}'::jsonb then return false; end if;
    foreach key in array keys loop
      if not public.profile_hub_integer(v->key,1,5) then return false; end if;
    end loop;
  elsif k = 'template' then
    keys := array['name','values'];
    if not p ?& keys or p - keys <> '{}'::jsonb
       or jsonb_typeof(p->'name') <> 'string' or length(p->>'name') not between 1 and 80 then return false; end if;
    v := p->'values'; keys := array['departure_origin','destinations','adults','child_count','preferences'];
    if jsonb_typeof(v) <> 'object' or not v ?& keys or v - keys <> '{}'::jsonb then return false; end if;
    if not (v->'departure_origin' = 'null'::jsonb or
       (jsonb_typeof(v->'departure_origin')='string' and v->>'departure_origin' ~ '^[a-zA-Z0-9_.:-]{1,128}$'))
       or not (v->'adults' = 'null'::jsonb or public.profile_hub_integer(v->'adults',1,100))
       or not public.profile_hub_integer(v->'child_count',0,20)
       or not public.profile_hub_payload_valid('preferences',v->'preferences')
       or v->'preferences' = 'null'::jsonb then return false; end if;
    if jsonb_typeof(v->'destinations') <> 'array' then return false; end if;
    if jsonb_array_length(v->'destinations') > 10 then return false; end if;
    if exists(select 1 from jsonb_array_elements(v->'destinations') as x(value)
      where jsonb_typeof(value) <> 'string' or value #>> '{}' !~ '^[a-zA-Z0-9_.:-]{1,128}$') then return false; end if;
  elsif k = 'saved_tour' then
    keys := array['title','supplier','url','comparison_id','column_id','offer_snapshot_id',
      'departure_date','price_label','evaluated_at','saved_at','status_at_save','note','collection'];
    if not p ?& keys or p - keys <> '{}'::jsonb then return false; end if;
    foreach key in array array['title','url','comparison_id','column_id','evaluated_at','saved_at','status_at_save','note','collection'] loop
      if jsonb_typeof(p->key) <> 'string' then return false; end if;
    end loop;
    if length(p->>'title') not between 1 and 500 or length(p->>'url') > 2048
       or p->>'url' !~ '^https?://[^/@[:space:]]+([/?#]|$)'
       or length(p->>'note') > 1000 or length(p->>'collection') > 80
       or p->>'status_at_save' not in ('recommended','needs_verification','reference') then return false; end if;
    foreach key in array array['comparison_id','column_id'] loop
      if p->>key !~ '^[a-zA-Z0-9_.:-]{1,128}$' then return false; end if;
    end loop;
    if not (p->'offer_snapshot_id' = 'null'::jsonb or
      (jsonb_typeof(p->'offer_snapshot_id')='string' and p->>'offer_snapshot_id' ~ '^[a-zA-Z0-9_.:-]{1,128}$')) then return false; end if;
    foreach key in array array['supplier','departure_date','price_label'] loop
      if p->key <> 'null'::jsonb and (jsonb_typeof(p->key) <> 'string' or
         length(p->>key) > case key when 'supplier' then 200 when 'departure_date' then 100 else 250 end) then return false; end if;
    end loop;
    foreach key in array array['evaluated_at','saved_at'] loop
      if p->>key !~ '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$'
         or not isfinite((p->>key)::timestamptz) then return false; end if;
    end loop;
  else return false;
  end if;
  return true;
exception when others then return false;
end;
$$;
revoke all on function public.profile_hub_integer(jsonb,integer,integer), public.profile_hub_payload_valid(text,jsonb) from public, anon, authenticated;
create table if not exists public.profile_hub_items (
  owner_id uuid not null references auth.users(id) on delete cascade,
  kind text not null check (kind in ('preferences', 'template', 'saved_tour')),
  item_id text not null check (length(item_id) between 1 and 128),
  version bigint not null default 1 check (version > 0),
  payload jsonb,
  deleted boolean not null default false,
  updated_at timestamptz not null default now(),
  primary key (owner_id, kind, item_id),
  check ((deleted and payload is null) or (not deleted and jsonb_typeof(payload) = 'object')),
  check (payload is null or octet_length(payload::text) <= 12000),
  check (kind <> 'preferences' or item_id = 'preferences'),
  constraint profile_hub_payload_valid check (public.profile_hub_payload_valid(kind,payload))
);
do $$ begin
  if not exists(select 1 from pg_constraint where conrelid='public.profile_hub_items'::regclass and conname='profile_hub_payload_valid') then
    alter table public.profile_hub_items add constraint profile_hub_payload_valid check (public.profile_hub_payload_valid(kind,payload));
  end if;
end $$;
create table if not exists public.profile_hub_receipts (
  owner_id uuid not null references auth.users(id) on delete cascade,
  mutation_key text not null,
  request_hash text not null,
  result jsonb not null,
  expires_at timestamptz not null default (now() + interval '24 hours'),
  primary key (owner_id, mutation_key)
);
alter table public.profile_hub_items enable row level security;
alter table public.profile_hub_receipts enable row level security;
drop policy if exists profile_hub_read_own on public.profile_hub_items;
create policy profile_hub_read_own on public.profile_hub_items for select to authenticated
  using (owner_id = (select auth.uid()));
drop policy if exists profile_hub_receipts_read_own on public.profile_hub_receipts;
create policy profile_hub_receipts_read_own on public.profile_hub_receipts for select to authenticated
  using (owner_id = (select auth.uid()) and expires_at > now());
revoke all on public.profile_hub_items, public.profile_hub_receipts from public, anon, authenticated;
grant select on public.profile_hub_items, public.profile_hub_receipts to authenticated;

create or replace function public.profile_hub_mutate(
  p_kind text, p_item_id text, p_expected_version bigint, p_payload jsonb,
  p_key text, p_request_hash text
) returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  v_owner uuid := auth.uid();
  v_row public.profile_hub_items;
  v_receipt public.profile_hub_receipts;
  v_result jsonb;
  v_limit int;
begin
  if v_owner is null then raise insufficient_privilege; end if;
  if p_kind is null or p_kind not in ('preferences','template','saved_tour')
     or p_item_id is null or p_item_id !~ '^[a-zA-Z0-9_.:-]{1,128}$'
     or (p_kind = 'preferences' and p_item_id <> 'preferences')
     or p_expected_version is null or p_expected_version < 0
     or p_key is null or p_key !~ '^[!-~]{1,128}$'
     or p_request_hash is null or p_request_hash !~ '^[a-f0-9]{64}$'
     or (p_payload is not null and (jsonb_typeof(p_payload) <> 'object' or octet_length(p_payload::text) > 12000))
     or not public.profile_hub_payload_valid(p_kind,p_payload)
  then return jsonb_build_object('error','INVALID_INPUT'); end if;
  -- Serialize same-owner creation, CAS, capacity and receipts together.
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(v_owner::text, 0));
  delete from public.profile_hub_receipts where owner_id=v_owner and expires_at<=now();
  select * into v_receipt from public.profile_hub_receipts where owner_id=v_owner and mutation_key=p_key;
  if found then
    if v_receipt.request_hash <> p_request_hash then return jsonb_build_object('error','IDEMPOTENCY_CONFLICT'); end if;
    return v_receipt.result;
  end if;
  select * into v_row from public.profile_hub_items where owner_id=v_owner and kind=p_kind and item_id=p_item_id;
  if coalesce(v_row.version,0) <> p_expected_version then
    return jsonb_build_object('error','VERSION_CONFLICT');
  end if;
  v_limit := case p_kind when 'preferences' then 1 when 'template' then 20 else 40 end;
  if p_payload is not null and (v_row.version is null or v_row.deleted) and
     (select count(*) from public.profile_hub_items where owner_id=v_owner and kind=p_kind and not deleted) >= v_limit
  then return jsonb_build_object('error','LIMIT_REACHED'); end if;
  -- Delete erases content immediately; tombstone retains version against stale writes.
  insert into public.profile_hub_items(owner_id,kind,item_id,version,payload,deleted,updated_at)
  values(v_owner,p_kind,p_item_id,p_expected_version+1,p_payload,p_payload is null,now())
  on conflict(owner_id,kind,item_id) do update set version=excluded.version,payload=excluded.payload,deleted=excluded.deleted,updated_at=excluded.updated_at
  returning * into v_row;
  v_result := jsonb_build_object('kind',v_row.kind,'item_id',v_row.item_id,'version',v_row.version,'payload',v_row.payload,'deleted',v_row.deleted,'updated_at',v_row.updated_at);
  -- A deletion must also erase content from old retry receipts for this item.
  if p_payload is null then
    delete from public.profile_hub_receipts where owner_id=v_owner and result->>'kind'=p_kind and result->>'item_id'=p_item_id;
  end if;
  insert into public.profile_hub_receipts(owner_id,mutation_key,request_hash,result) values(v_owner,p_key,p_request_hash,v_result);
  return v_result;
end;
$$;
revoke all on function public.profile_hub_mutate(text,text,bigint,jsonb,text,text) from public, anon;
grant execute on function public.profile_hub_mutate(text,text,bigint,jsonb,text,text) to authenticated;
notify pgrst, 'reload schema';
commit;
