-- Suporte a múltiplas contas Bling compartilhando o mesmo banco. Os
-- pedido_id/item_id do Bling são internos de cada conta (duas contas podem
-- gerar o mesmo número), então "conta" passa a fazer parte da chave em toda
-- tabela que hoje identifica um registro por pedido_id/item_id/canal.
-- Dados já existentes pertencem à conta "marketplaces" (única conectada até
-- aqui).

-- bling_tokens: passa a ter 1 linha por conta em vez de id fixo = 1
alter table public.bling_tokens add column if not exists conta text;
update public.bling_tokens set conta = 'marketplaces' where conta is null;
alter table public.bling_tokens alter column conta set not null;
alter table public.bling_tokens add constraint bling_tokens_conta_key unique (conta);

-- historico_diario
alter table public.historico_diario add column if not exists conta text;
update public.historico_diario set conta = 'marketplaces' where conta is null;
alter table public.historico_diario alter column conta set not null;
alter table public.historico_diario drop constraint if exists historico_diario_data_canal_key;
alter table public.historico_diario add constraint historico_diario_data_canal_conta_key unique (data, canal, conta);

-- itens_pedidos
alter table public.itens_pedidos add column if not exists conta text;
update public.itens_pedidos set conta = 'marketplaces' where conta is null;
alter table public.itens_pedidos alter column conta set not null;
alter table public.itens_pedidos drop constraint if exists itens_pedidos_pedido_id_item_id_key;
alter table public.itens_pedidos add constraint itens_pedidos_conta_pedido_item_key unique (conta, pedido_id, item_id);

-- pedidos_sincronizados: PK composta (conta, pedido_id) — antes era só pedido_id
alter table public.pedidos_sincronizados add column if not exists conta text;
update public.pedidos_sincronizados set conta = 'marketplaces' where conta is null;
alter table public.pedidos_sincronizados alter column conta set not null;
alter table public.pedidos_sincronizados drop constraint pedidos_sincronizados_pkey;
alter table public.pedidos_sincronizados add primary key (conta, pedido_id);

-- metas
alter table public.metas add column if not exists conta text;
update public.metas set conta = 'marketplaces' where conta is null;
alter table public.metas alter column conta set not null;
alter table public.metas drop constraint if exists metas_canal_referencia_inicio_referencia_fim_key;
alter table public.metas add constraint metas_conta_canal_periodo_key unique (conta, canal, referencia_inicio, referencia_fim);
