create table if not exists world_regions (
  id uuid primary key default gen_random_uuid(),
  pet_id uuid not null references pets(id) on delete cascade,
  name text not null,
  description text,
  tags text[] default '{}',
  status text not null default 'planned'
    check (status in ('planned', 'in_progress', 'complete', 'needs_revision')),
  bounds_min_x int not null,
  bounds_min_y int not null,
  bounds_min_z int not null,
  bounds_max_x int not null,
  bounds_max_y int not null,
  bounds_max_z int not null,
  relationships jsonb default '{}',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
create index idx_world_regions_pet on world_regions(pet_id);
create index idx_world_regions_status on world_regions(pet_id, status);
