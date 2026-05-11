create table if not exists world_journal (
  id uuid primary key default gen_random_uuid(),
  pet_id uuid not null references pets(id) on delete cascade,
  creative_brief text,
  build_plan jsonb,
  critic_review jsonb,
  region_id uuid references world_regions(id) on delete set null,
  voxels_placed int default 0,
  created_at timestamptz default now()
);
create index idx_world_journal_pet on world_journal(pet_id);
create index idx_world_journal_created on world_journal(pet_id, created_at desc);
