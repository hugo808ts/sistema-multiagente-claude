-- Agente Estoque e Compras
-- Valores em centavos (inteiros) para evitar erro de arredondamento.

CREATE TABLE IF NOT EXISTS produtos (
    id             INTEGER PRIMARY KEY,
    nome           TEXT    NOT NULL UNIQUE,
    unidade        TEXT    NOT NULL,              -- kg, un, pct, cx
    estoque_minimo REAL    NOT NULL DEFAULT 0,
    ativo          INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS fornecedores (
    id      INTEGER PRIMARY KEY,
    nome    TEXT NOT NULL UNIQUE,
    contato TEXT
);

CREATE TABLE IF NOT EXISTS movimentacoes (
    id                      INTEGER PRIMARY KEY,
    produto_id              INTEGER NOT NULL REFERENCES produtos(id),
    tipo                    TEXT    NOT NULL CHECK (tipo IN ('entrada', 'saida')),
    quantidade              REAL    NOT NULL CHECK (quantidade > 0),
    custo_unitario_centavos INTEGER,              -- obrigatório na entrada
    fornecedor_id           INTEGER REFERENCES fornecedores(id),
    data                    TEXT    NOT NULL DEFAULT (date('now')),
    observacao              TEXT,
    CHECK (tipo = 'saida' OR custo_unitario_centavos IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS cotacoes (
    id             INTEGER PRIMARY KEY,
    produto_id     INTEGER NOT NULL REFERENCES produtos(id),
    fornecedor_id  INTEGER NOT NULL REFERENCES fornecedores(id),
    preco_centavos INTEGER NOT NULL CHECK (preco_centavos > 0),
    data           TEXT    NOT NULL DEFAULT (date('now'))
);

CREATE INDEX IF NOT EXISTS ix_mov_produto ON movimentacoes(produto_id);

-- Saldo atual e custo médio ponderado das entradas
CREATE VIEW IF NOT EXISTS vw_saldo AS
SELECT p.id, p.nome, p.unidade, p.estoque_minimo,
       COALESCE(SUM(CASE WHEN m.tipo = 'entrada' THEN m.quantidade ELSE -m.quantidade END), 0) AS saldo,
       CAST(ROUND(
           SUM(CASE WHEN m.tipo = 'entrada' THEN m.quantidade * m.custo_unitario_centavos END)
           / NULLIF(SUM(CASE WHEN m.tipo = 'entrada' THEN m.quantidade END), 0)
       ) AS INTEGER) AS custo_medio_centavos
FROM produtos p
LEFT JOIN movimentacoes m ON m.produto_id = p.id
WHERE p.ativo = 1
GROUP BY p.id;

-- Produtos no mínimo ou abaixo dele
CREATE VIEW IF NOT EXISTS vw_reposicao AS
SELECT * FROM vw_saldo WHERE saldo <= estoque_minimo;

-- Menor preço por produto nas cotações dos últimos 30 dias
CREATE VIEW IF NOT EXISTS vw_melhor_cotacao AS
SELECT p.nome AS produto, f.nome AS fornecedor, MIN(c.preco_centavos) AS preco_centavos, c.data
FROM cotacoes c
JOIN produtos p     ON p.id = c.produto_id
JOIN fornecedores f ON f.id = c.fornecedor_id
WHERE c.data >= date('now', '-30 day')
GROUP BY c.produto_id;
