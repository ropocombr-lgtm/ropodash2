create table if not exists public.historico_diario (
    id bigint generated always as identity primary key,
    data date not null,
    canal text not null,
    pedidos integer not null default 0,
    cancelados integer not null default 0,
    faturamento_bruto numeric not null default 0,
    faturamento_valido numeric not null default 0,
    updated_at timestamptz not null default now(),
    unique (data, canal)
);

alter table public.historico_diario enable row level security;
