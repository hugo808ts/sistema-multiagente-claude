-- =========================================================
-- Agente Finanças — schema do banco (SQLite)
-- Valores SEMPRE em centavos (INTEGER). Datas em 'YYYY-MM-DD'.
-- =========================================================
PRAGMA foreign_keys = ON;

-- Lugares onde o dinheiro fica (conta corrente, poupança, caixinha, corretora, carteira física)
CREATE TABLE IF NOT EXISTS contas (
    id           INTEGER PRIMARY KEY,
    nome         TEXT NOT NULL UNIQUE,              -- apelido: "Banco A corrente", "Banco B caixinha"
    instituicao  TEXT NOT NULL,                     -- "Banco A", "Corretora", "Dinheiro"
    tipo         TEXT NOT NULL CHECK (tipo IN ('corrente','poupanca','reserva','corretora','carteira','beneficio')),
    ativa        INTEGER NOT NULL DEFAULT 1,
    obs          TEXT
);

-- Cartões de crédito
CREATE TABLE IF NOT EXISTS cartoes (
    id               INTEGER PRIMARY KEY,
    nome             TEXT NOT NULL UNIQUE,          -- "Banco B crédito"
    instituicao      TEXT NOT NULL,
    limite_centavos  INTEGER NOT NULL,
    dia_fechamento   INTEGER NOT NULL CHECK (dia_fechamento BETWEEN 1 AND 31),
    dia_vencimento   INTEGER NOT NULL CHECK (dia_vencimento BETWEEN 1 AND 31),
    conta_pagamento_id INTEGER REFERENCES contas(id),
    ativo            INTEGER NOT NULL DEFAULT 1,
    meta_mensal_centavos INTEGER                   -- teto de gasto por fatura definido pelo usuário
);

-- Categorias (com subcategoria opcional via pai_id)
CREATE TABLE IF NOT EXISTS categorias (
    id      INTEGER PRIMARY KEY,
    nome    TEXT NOT NULL UNIQUE,
    tipo    TEXT NOT NULL CHECK (tipo IN ('gasto','receita')),
    pai_id  INTEGER REFERENCES categorias(id)
);

-- Coração do banco: toda movimentação de dinheiro
-- valor_centavos é sempre POSITIVO; o 'tipo' define a direção.
-- Exceção: tipo 'ajuste' pode ser negativo.
CREATE TABLE IF NOT EXISTS movimentacoes (
    id                INTEGER PRIMARY KEY,
    data              TEXT NOT NULL,                -- dia da compra/movimento
    descricao         TEXT NOT NULL,
    valor_centavos    INTEGER NOT NULL,
    tipo              TEXT NOT NULL CHECK (tipo IN (
                         'gasto',            -- saída (conta ou cartão)
                         'receita',          -- entrada (salário, pix recebido)
                         'transferencia',    -- conta -> conta_destino
                         'aporte',           -- conta -> investimento (detalhe em operacoes_invest)
                         'resgate',          -- investimento -> conta
                         'pagamento_fatura', -- conta paga fatura do cartao
                         'estorno',          -- devolução no cartão/conta
                         'ajuste')),         -- correção / saldo inicial de cartão
    categoria_id      INTEGER REFERENCES categorias(id),
    conta_id          INTEGER REFERENCES contas(id),     -- origem (ou conta afetada)
    conta_destino_id  INTEGER REFERENCES contas(id),     -- só transferência/resgate
    cartao_id         INTEGER REFERENCES cartoes(id),    -- se foi no crédito / pagamento de fatura
    fatura_mes        TEXT,                              -- 'YYYY-MM' da fatura em que cai (só cartão)
    parcela_num       INTEGER,
    parcela_total     INTEGER,
    grupo_parcela     TEXT,                              -- mesmo valor p/ todas as parcelas de uma compra
    obs               TEXT,
    criado_em         TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    CHECK (valor_centavos > 0 OR tipo = 'ajuste'),
    CHECK (conta_id IS NOT NULL OR cartao_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS ix_mov_data      ON movimentacoes(data);
CREATE INDEX IF NOT EXISTS ix_mov_conta     ON movimentacoes(conta_id, data);
CREATE INDEX IF NOT EXISTS ix_mov_cartao    ON movimentacoes(cartao_id, fatura_mes);
CREATE INDEX IF NOT EXISTS ix_mov_categoria ON movimentacoes(categoria_id, data);

-- "Hoje tenho X na conta tal" — ponto de partida e conferência
-- Regra: o saldo vale para o FIM do dia informado.
CREATE TABLE IF NOT EXISTS saldos_registrados (
    id              INTEGER PRIMARY KEY,
    conta_id        INTEGER NOT NULL REFERENCES contas(id),
    data            TEXT NOT NULL,
    saldo_centavos  INTEGER NOT NULL,
    obs             TEXT,
    UNIQUE (conta_id, data)
);

-- Contas fixas / recorrentes (assinaturas, academia, aluguel...)
CREATE TABLE IF NOT EXISTS contas_fixas (
    id              INTEGER PRIMARY KEY,
    descricao       TEXT NOT NULL,
    valor_centavos  INTEGER NOT NULL,
    dia             INTEGER NOT NULL CHECK (dia BETWEEN 1 AND 31),   -- dia da cobrança
    forma           TEXT NOT NULL CHECK (forma IN ('cartao','pix','debito','boleto')),
    cartao_id       INTEGER REFERENCES cartoes(id),
    conta_id        INTEGER REFERENCES contas(id),
    categoria_id    INTEGER REFERENCES categorias(id),
    inicio          TEXT,                                            -- 1ª cobrança 'YYYY-MM-DD'
    ativa           INTEGER NOT NULL DEFAULT 1,
    obs             TEXT
);

-- Ativos de investimento (FII, ação, tesouro, CDB...)
CREATE TABLE IF NOT EXISTS ativos (
    id      INTEGER PRIMARY KEY,
    codigo  TEXT NOT NULL UNIQUE,                 -- "KNSC11", "TESOURO SELIC 2029", "CDB 110% CDI"
    classe  TEXT NOT NULL CHECK (classe IN ('fii','acao','etf','renda_fixa','tesouro','cripto','outro')),
    obs     TEXT
);

-- Operações de investimento (compra, venda, rendimento/dividendo)
CREATE TABLE IF NOT EXISTS operacoes_invest (
    id                   INTEGER PRIMARY KEY,
    data                 TEXT NOT NULL,
    ativo_id             INTEGER NOT NULL REFERENCES ativos(id),
    conta_id             INTEGER NOT NULL REFERENCES contas(id),   -- corretora/banco onde está
    tipo                 TEXT NOT NULL CHECK (tipo IN ('compra','venda','rendimento','posicao_inicial')),
    quantidade           REAL NOT NULL DEFAULT 0,
    valor_total_centavos INTEGER NOT NULL,
    obs                  TEXT
);
CREATE INDEX IF NOT EXISTS ix_inv_ativo ON operacoes_invest(ativo_id, data);

-- =========================================================
-- VIEWS (consultas prontas)
-- =========================================================

-- Saldo atual de cada conta = último saldo registrado + movimentações depois dele
CREATE VIEW IF NOT EXISTS v_saldo_contas AS
WITH ult AS (
    SELECT s.conta_id, s.data, s.saldo_centavos
    FROM saldos_registrados s
    WHERE s.data = (SELECT MAX(data) FROM saldos_registrados WHERE conta_id = s.conta_id)
),
mov AS (
    SELECT m.conta_id AS cid, m.data,
           CASE m.tipo
               WHEN 'receita' THEN  m.valor_centavos
               WHEN 'resgate' THEN  0
               WHEN 'estorno' THEN  m.valor_centavos
               WHEN 'ajuste'  THEN  m.valor_centavos
               ELSE -m.valor_centavos
           END AS delta
    FROM movimentacoes m
    WHERE m.conta_id IS NOT NULL AND m.cartao_id IS NULL
       OR (m.tipo = 'pagamento_fatura' AND m.conta_id IS NOT NULL)
    UNION ALL
    SELECT m.conta_destino_id, m.data, m.valor_centavos
    FROM movimentacoes m
    WHERE m.tipo IN ('transferencia','resgate') AND m.conta_destino_id IS NOT NULL
)
SELECT c.id AS conta_id, c.nome, c.instituicao, c.tipo,
       u.data AS data_ultimo_registro,
       COALESCE(u.saldo_centavos,0) +
       COALESCE((SELECT SUM(delta) FROM mov WHERE mov.cid = c.id AND mov.data > COALESCE(u.data,'0000-00-00')),0)
       AS saldo_centavos
FROM contas c LEFT JOIN ult u ON u.conta_id = c.id
WHERE c.ativa = 1;

-- Limite dos cartões: usado = compras (inclui parcelas futuras) - estornos - pagamentos + ajustes
CREATE VIEW IF NOT EXISTS v_limite_cartoes AS
SELECT k.id AS cartao_id, k.nome, k.limite_centavos,
       COALESCE(SUM(CASE m.tipo
            WHEN 'gasto'            THEN  m.valor_centavos
            WHEN 'ajuste'           THEN  m.valor_centavos
            WHEN 'estorno'          THEN -m.valor_centavos
            WHEN 'pagamento_fatura' THEN -m.valor_centavos
            ELSE 0 END),0) AS usado_centavos,
       k.limite_centavos - COALESCE(SUM(CASE m.tipo
            WHEN 'gasto'            THEN  m.valor_centavos
            WHEN 'ajuste'           THEN  m.valor_centavos
            WHEN 'estorno'          THEN -m.valor_centavos
            WHEN 'pagamento_fatura' THEN -m.valor_centavos
            ELSE 0 END),0) AS disponivel_centavos
FROM cartoes k LEFT JOIN movimentacoes m ON m.cartao_id = k.id
WHERE k.ativo = 1
GROUP BY k.id;

-- Valor de cada fatura (por cartão e mês)
CREATE VIEW IF NOT EXISTS v_faturas AS
SELECT k.nome AS cartao, m.fatura_mes,
       SUM(CASE WHEN m.tipo IN ('gasto','ajuste') THEN m.valor_centavos
                WHEN m.tipo = 'estorno' THEN -m.valor_centavos ELSE 0 END) AS total_centavos
FROM movimentacoes m JOIN cartoes k ON k.id = m.cartao_id
WHERE m.fatura_mes IS NOT NULL AND m.tipo <> 'pagamento_fatura'
GROUP BY k.nome, m.fatura_mes;

-- Posição de investimentos (custo)
CREATE VIEW IF NOT EXISTS v_posicao_invest AS
SELECT a.codigo, a.classe, c.nome AS onde,
       SUM(CASE o.tipo WHEN 'compra' THEN o.quantidade WHEN 'posicao_inicial' THEN o.quantidade
                       WHEN 'venda' THEN -o.quantidade ELSE 0 END) AS quantidade,
       SUM(CASE o.tipo WHEN 'compra' THEN o.valor_total_centavos WHEN 'posicao_inicial' THEN o.valor_total_centavos
                       WHEN 'venda' THEN -o.valor_total_centavos ELSE 0 END) AS custo_centavos,
       SUM(CASE WHEN o.tipo = 'rendimento' THEN o.valor_total_centavos ELSE 0 END) AS rendimentos_centavos
FROM operacoes_invest o
JOIN ativos a ON a.id = o.ativo_id
JOIN contas c ON c.id = o.conta_id
GROUP BY a.id, c.id;

-- Gastos por mês e categoria (base de relatórios)
CREATE VIEW IF NOT EXISTS v_gastos_mes_categoria AS
SELECT substr(m.data,1,7) AS mes,
       COALESCE(p.nome, cat.nome, 'Sem categoria') AS categoria,
       SUM(m.valor_centavos) AS total_centavos,
       COUNT(*) AS qtd
FROM movimentacoes m
LEFT JOIN categorias cat ON cat.id = m.categoria_id
LEFT JOIN categorias p   ON p.id = cat.pai_id
WHERE m.tipo = 'gasto'
GROUP BY mes, categoria;

-- =========================================================
-- Categorias iniciais (o usuário pode pedir para mudar)
-- =========================================================
INSERT OR IGNORE INTO categorias (nome, tipo) VALUES
 ('Alimentação','gasto'), ('Mercado','gasto'), ('Delivery','gasto'),
 ('Transporte','gasto'), ('Moradia','gasto'), ('Contas fixas','gasto'),
 ('Assinaturas','gasto'), ('Saúde','gasto'), ('Educação','gasto'),
 ('Lazer','gasto'), ('Compras','gasto'), ('Presentes','gasto'),
 ('Taxas e juros','gasto'), ('Outros gastos','gasto'),
 ('Salário','receita'), ('Rendimentos','receita'), ('Reembolso','receita'),
 ('Pix recebido','receita'), ('Outras receitas','receita');

UPDATE categorias SET pai_id = (SELECT id FROM categorias WHERE nome='Alimentação')
 WHERE nome IN ('Mercado','Delivery');
