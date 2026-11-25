-- Agente Financeiro: contas a pagar e a receber da empresa
-- Valores em centavos (inteiros).

CREATE TABLE IF NOT EXISTS contas (
    id             INTEGER PRIMARY KEY,
    tipo           TEXT    NOT NULL CHECK (tipo IN ('pagar', 'receber')),
    descricao      TEXT    NOT NULL,
    parte          TEXT    NOT NULL,              -- fornecedor ou cliente
    centro_custo   TEXT    NOT NULL,              -- ex.: insumos, folha, logistica, vendas
    valor_centavos INTEGER NOT NULL CHECK (valor_centavos > 0),
    vencimento     TEXT    NOT NULL,              -- AAAA-MM-DD
    pago_em        TEXT                           -- NULL = em aberto
);

CREATE INDEX IF NOT EXISTS ix_contas_venc ON contas(vencimento);

CREATE VIEW IF NOT EXISTS vw_em_aberto AS
SELECT *, CASE WHEN vencimento < date('now') THEN 1 ELSE 0 END AS vencida
FROM contas
WHERE pago_em IS NULL;

-- Realizado por mês (pelo dia do pagamento)
CREATE VIEW IF NOT EXISTS vw_fluxo_mensal AS
SELECT substr(pago_em, 1, 7) AS mes,
       SUM(CASE WHEN tipo = 'receber' THEN valor_centavos ELSE 0 END) AS entradas,
       SUM(CASE WHEN tipo = 'pagar'   THEN valor_centavos ELSE 0 END) AS saidas,
       SUM(CASE WHEN tipo = 'receber' THEN valor_centavos ELSE -valor_centavos END) AS saldo
FROM contas
WHERE pago_em IS NOT NULL
GROUP BY mes;

-- Despesas pagas por centro de custo e mês
CREATE VIEW IF NOT EXISTS vw_despesas_centro AS
SELECT substr(pago_em, 1, 7) AS mes, centro_custo, SUM(valor_centavos) AS total
FROM contas
WHERE tipo = 'pagar' AND pago_em IS NOT NULL
GROUP BY mes, centro_custo;
