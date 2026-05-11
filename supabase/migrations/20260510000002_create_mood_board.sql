create table if not exists pet_mood_board (
  id uuid primary key default gen_random_uuid(),
  pet_id uuid not null references pets(id) on delete cascade,
  theme text not null,
  weight float not null default 1.0,
  moments text[] default '{}',
  first_seen timestamptz default now(),
  last_seen timestamptz default now(),
  mention_count int default 1,
  unique(pet_id, theme)
);
create index idx_mood_board_pet on pet_mood_board(pet_id);
create index idx_mood_board_weight on pet_mood_board(pet_id, weight desc);
