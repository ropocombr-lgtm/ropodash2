-- A tabela metas estava vazia (nenhuma meta real cadastrada ainda), então
-- redesenhamos o esquema em vez de migrar: períodos de meta passam a ter
-- início/fim explícitos, em vez de assumir semana ISO (segunda a domingo)
-- ou mês calendário — o que não representa corretamente semanas truncadas
-- no início/fim do mês.
drop table if exists public.metas;

create table public.metas (
    id bigint generated always as identity primary key,
    canal text not null,
    referencia_inicio date not null,
    referencia_fim date not null,
    valor numeric not null check (valor >= 0),
    rotulo text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (canal, referencia_inicio, referencia_fim)
);

alter table public.metas enable row level security;
