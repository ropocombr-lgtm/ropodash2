-- Reverte 006_multi_conta_bling.sql. O multi-conta nunca chegou a ter uma
-- segunda conta de fato conectada (todos os dados existentes são
-- 'marketplaces', exceto 1 linha de teste 'manual' em historico_diario, que
-- não colide com nada e fica só sem a coluna). Confirmado sem duplicidade em
-- nenhuma das 5 tabelas antes de rodar isto.

-- bling_tokens: volta a ter 1 linha fixa (id = 1)
alter table public.bling_tokens drop constraint if exists bling_tokens_conta_key;
alter table public.bling_tokens drop column if exists conta;

-- historico_diario
alter table public.historico_diario drop constraint if exists historico_diario_data_canal_conta_key;
alter table public.historico_diario drop column if exists conta;
alter table public.historico_diario add constraint historico_diario_data_canal_key unique (data, canal);

-- itens_pedidos
alter table public.itens_pedidos drop constraint if exists itens_pedidos_conta_pedido_item_key;
alter table public.itens_pedidos drop column if exists conta;
alter table public.itens_pedidos add constraint itens_pedidos_pedido_id_item_id_key unique (pedido_id, item_id);

-- pedidos_sincronizados: PK volta a ser só pedido_id
alter table public.pedidos_sincronizados drop constraint if exists pedidos_sincronizados_pkey;
alter table public.pedidos_sincronizados drop column if exists conta;
alter table public.pedidos_sincronizados add primary key (pedido_id);

-- metas
alter table public.metas drop constraint if exists metas_conta_canal_periodo_key;
alter table public.metas drop column if exists conta;
alter table public.metas add constraint metas_canal_referencia_inicio_referencia_fim_key unique (canal, referencia_inicio, referencia_fim);
