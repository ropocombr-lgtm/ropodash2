create table if not exists public.itens_pedidos (
    id bigint generated always as identity primary key,
    pedido_id bigint not null,
    item_id bigint not null,
    produto_id bigint,
    sku text,
    descricao text,
    quantidade numeric not null default 0,
    valor_unitario numeric not null default 0,
    desconto numeric not null default 0,
    data date not null,
    canal text not null,
    situacao_id integer,
    updated_at timestamptz not null default now(),
    unique (pedido_id, item_id)
);

create index if not exists itens_pedidos_pedido_id_idx
    on public.itens_pedidos (pedido_id);

create index if not exists itens_pedidos_data_idx
    on public.itens_pedidos (data);

alter table public.itens_pedidos enable row level security;

-- Controla quais pedidos já tiveram os itens sincronizados, para não
-- precisar rechamar o endpoint de detalhe do Bling a cada atualização.
create table if not exists public.pedidos_sincronizados (
    pedido_id bigint primary key,
    sincronizado_em timestamptz not null default now()
);

alter table public.pedidos_sincronizados enable row level security;
