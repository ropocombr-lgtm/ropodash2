-- Pedidos de B2B fechados fora do Bling (ex.: distribuidor, atacado direto,
-- WhatsApp) que não têm integração automática com o ERP. Cadastrados à mão
-- pela equipe comercial e somados ao restante do faturamento no dashboard.
create table if not exists public.pedidos_manuais (
    id bigint generated always as identity primary key,
    data date not null,
    cliente text not null,
    canal text not null,
    situacao text not null default 'Atendido' check (situacao in ('Atendido', 'Cancelado')),
    total numeric not null check (total >= 0),
    observacoes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists pedidos_manuais_data_idx
    on public.pedidos_manuais (data);

alter table public.pedidos_manuais enable row level security;
