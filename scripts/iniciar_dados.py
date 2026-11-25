"""Cria os bancos dos agentes em dados/ e, com --demo, carrega dados fictícios.

    python scripts/iniciar_dados.py          # bancos vazios
    python scripts/iniciar_dados.py --demo   # bancos com dados de exemplo

Todos os dados de demonstração são fictícios (empresa "Cozinha Exemplo").
"""
import argparse
import datetime
import os
import sys

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, RAIZ)
from nucleo.db import caminho_banco, conectar, iniciar  # noqa: E402

AGENTES = {
    "estoque": "agentes/AGENTE_ESTOQUE/schema.sql",
    "atendimento": "agentes/AGENTE_ATENDIMENTO/schema.sql",
    "financeiro": "agentes/AGENTE_FINANCEIRO/schema.sql",
}


def dia(delta: int) -> str:
    return (datetime.date.today() + datetime.timedelta(days=delta)).isoformat()


def carregar_demo():
    with conectar("estoque") as c:
        c.executemany("INSERT INTO produtos (nome, unidade, estoque_minimo) VALUES (?, ?, ?)", [
            ("Arroz 5kg", "pct", 10), ("Feijão 1kg", "pct", 15), ("Óleo de soja 900ml", "un", 12),
            ("Frango congelado", "kg", 30), ("Embalagem marmita", "un", 200)])
        c.executemany("INSERT INTO fornecedores (nome, contato) VALUES (?, ?)", [
            ("Atacado Alfa", "compras@alfa.exemplo"), ("Distribuidora Beta", "vendas@beta.exemplo")])
        c.executemany("INSERT INTO movimentacoes (produto_id, tipo, quantidade, custo_unitario_centavos, fornecedor_id, data)"
                      " VALUES (?, ?, ?, ?, ?, ?)", [
            (1, "entrada", 20, 2490, 1, dia(-10)), (1, "entrada", 10, 2350, 2, dia(-3)), (1, "saida", 18, None, None, dia(-1)),
            (2, "entrada", 30, 790, 1, dia(-8)), (2, "saida", 12, None, None, dia(-1)),
            (3, "entrada", 24, 699, 2, dia(-8)), (3, "saida", 14, None, None, dia(-1)),
            (4, "entrada", 80, 1290, 2, dia(-5)), (4, "saida", 45, None, None, dia(-1)),
            (5, "entrada", 500, 45, 1, dia(-6)), (5, "saida", 260, None, None, dia(-1))])
        c.executemany("INSERT INTO cotacoes (produto_id, fornecedor_id, preco_centavos, data) VALUES (?, ?, ?, ?)", [
            (1, 1, 2450, dia(-2)), (1, 2, 2320, dia(-2)), (4, 1, 1240, dia(-2)), (4, 2, 1310, dia(-2))])

    with conectar("atendimento") as c:
        c.executemany("INSERT INTO clientes (nome, contato) VALUES (?, ?)", [
            ("Unidade Centro", "centro@cliente.exemplo"), ("Unidade Norte", "norte@cliente.exemplo")])
        c.execute("INSERT INTO pedidos (cliente_id, data_entrega, refeicao, mensagem) VALUES (1, ?, 'almoco', ?)",
                  (dia(1), "Bom dia! Pra amanhã no almoço: 40 marmitas executivas e 10 vegetarianas."))
        c.executemany("INSERT INTO itens_pedido (pedido_id, item, quantidade) VALUES (1, ?, ?)",
                      [("Marmita executiva", 40), ("Marmita vegetariana", 10)])

    with conectar("financeiro") as c:
        c.executemany("INSERT INTO contas (tipo, descricao, parte, centro_custo, valor_centavos, vencimento, pago_em)"
                      " VALUES (?, ?, ?, ?, ?, ?, ?)", [
            ("pagar", "NF 1042 - arroz e feijão", "Atacado Alfa", "insumos", 73500, dia(-5), dia(-5)),
            ("pagar", "NF 2210 - frango", "Distribuidora Beta", "insumos", 103200, dia(3), None),
            ("pagar", "Frete semanal", "Transportes Gama", "logistica", 18000, dia(-1), None),
            ("receber", "Contrato mensal", "Unidade Centro", "vendas", 950000, dia(-4), dia(-4)),
            ("receber", "Contrato mensal", "Unidade Norte", "vendas", 720000, dia(6), None)])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--demo", action="store_true", help="carrega dados fictícios")
    a = p.parse_args()
    if a.demo and any(os.path.exists(caminho_banco(ag)) for ag in AGENTES):
        sys.exit("Já existem bancos em dados/. Apague-os antes de carregar a demonstração.")
    for agente, schema in AGENTES.items():
        iniciar(agente, os.path.join(RAIZ, schema))
        print("Banco pronto:", caminho_banco(agente))
    if a.demo:
        carregar_demo()
        print("Dados de demonstração carregados.")


if __name__ == "__main__":
    main()
