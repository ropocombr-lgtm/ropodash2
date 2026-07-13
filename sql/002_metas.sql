create table if not exists public.metas (
    id bigint generated always as identity primary key,
    canal text not null,
    periodicidade text not null check (periodicidade in ('semanal', 'mensal')),
    referencia date not null,
    valor numeric not null check (valor >= 0),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (canal, periodicidade, referencia)
);

alter table public.metas enable row level security;
