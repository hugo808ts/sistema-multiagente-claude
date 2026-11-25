-- Agente Atendimento: pedidos recebidos de clientes por mensagem

CREATE TABLE IF NOT EXISTS clientes (
    id      INTEGER PRIMARY KEY,
    nome    TEXT NOT NULL UNIQUE,
    contato TEXT
);

CREATE TABLE IF NOT EXISTS pedidos (
    id            INTEGER PRIMARY KEY,
    cliente_id    INTEGER NOT NULL REFERENCES clientes(id),
    data_entrega  TEXT    NOT NULL,                 -- AAAA-MM-DD
    refeicao      TEXT    NOT NULL CHECK (refeicao IN ('cafe', 'almoco', 'jantar')),
    status        TEXT    NOT NULL DEFAULT 'confirmado'
                          CHECK (status IN ('confirmado', 'cancelado', 'entregue')),
    mensagem      TEXT,                             -- texto original do cliente
    criado_em     TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS itens_pedido (
    id         INTEGER PRIMARY KEY,
    pedido_id  INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
    item       TEXT    NOT NULL,
    quantidade INTEGER NOT NULL CHECK (quantidade > 0)
);

-- Total por item e dia (base para produção e etiquetas)
CREATE VIEW IF NOT EXISTS vw_producao_dia AS
SELECT p.data_entrega, p.refeicao, i.item, SUM(i.quantidade) AS total
FROM pedidos p
JOIN itens_pedido i ON i.pedido_id = p.id
WHERE p.status = 'confirmado'
GROUP BY p.data_entrega, p.refeicao, i.item;
