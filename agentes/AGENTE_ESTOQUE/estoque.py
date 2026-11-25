"""Ferramentas do Agente Estoque e Compras.

Leitura:
    python estoque.py saldo
    python estoque.py repor
    python estoque.py cotacoes

Escrita (mostra a prévia; só grava com --confirmar, depois do OK humano):
    python estoque.py entrada --produto "Arroz 5kg" --qtd 10 --custo 24.90 --fornecedor "Atacado Alfa"
    python estoque.py saida   --produto "Arroz 5kg" --qtd 3
    python estoque.py cotacao --produto "Arroz 5kg" --fornecedor "Atacado Alfa" --preco 23.50
"""
import argparse
import os
import sys

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, RAIZ)
from nucleo.db import backup, conectar, iniciar, reais  # noqa: E402

AGENTE = "estoque"
SCHEMA = os.path.join(os.path.dirname(__file__), "schema.sql")


class ErroEstoque(Exception):
    pass


def _db():
    iniciar(AGENTE, SCHEMA)
    return conectar(AGENTE)


def _id(c, tabela, nome):
    linha = c.execute(f"SELECT id FROM {tabela} WHERE nome = ?", (nome,)).fetchone()
    if not linha:
        raise ErroEstoque(f"'{nome}' não encontrado em {tabela}.")
    return linha["id"]


def saldo():
    with _db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM vw_saldo ORDER BY nome")]


def itens_para_repor():
    with _db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM vw_reposicao ORDER BY nome")]


def melhores_cotacoes():
    with _db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM vw_melhor_cotacao ORDER BY produto")]


def registrar_entrada(produto, qtd, custo_centavos, fornecedor=None, confirmar=False):
    with _db() as c:
        pid = _id(c, "produtos", produto)
        fid = _id(c, "fornecedores", fornecedor) if fornecedor else None
        previa = {"acao": "entrada", "produto": produto, "quantidade": qtd,
                  "custo_unitario": reais(custo_centavos), "fornecedor": fornecedor}
        if not confirmar:
            return {"previa": previa, "gravado": False}
        backup(AGENTE)
        c.execute("INSERT INTO movimentacoes (produto_id, tipo, quantidade, custo_unitario_centavos, fornecedor_id)"
                  " VALUES (?, 'entrada', ?, ?, ?)", (pid, qtd, custo_centavos, fid))
        return {"previa": previa, "gravado": True}


def registrar_saida(produto, qtd, confirmar=False):
    with _db() as c:
        pid = _id(c, "produtos", produto)
        atual = c.execute("SELECT saldo FROM vw_saldo WHERE id = ?", (pid,)).fetchone()["saldo"]
        if qtd > atual:
            raise ErroEstoque(f"Saldo insuficiente de {produto}: {atual} disponível, {qtd} pedido.")
        previa = {"acao": "saida", "produto": produto, "quantidade": qtd, "saldo_depois": atual - qtd}
        if not confirmar:
            return {"previa": previa, "gravado": False}
        backup(AGENTE)
        c.execute("INSERT INTO movimentacoes (produto_id, tipo, quantidade) VALUES (?, 'saida', ?)", (pid, qtd))
        return {"previa": previa, "gravado": True}


def registrar_cotacao(produto, fornecedor, preco_centavos, confirmar=False):
    with _db() as c:
        pid, fid = _id(c, "produtos", produto), _id(c, "fornecedores", fornecedor)
        previa = {"acao": "cotacao", "produto": produto, "fornecedor": fornecedor, "preco": reais(preco_centavos)}
        if not confirmar:
            return {"previa": previa, "gravado": False}
        backup(AGENTE)
        c.execute("INSERT INTO cotacoes (produto_id, fornecedor_id, preco_centavos) VALUES (?, ?, ?)",
                  (pid, fid, preco_centavos))
        return {"previa": previa, "gravado": True}


def _centavos(valor: str) -> int:
    return round(float(valor.replace(",", ".")) * 100)


def main():
    p = argparse.ArgumentParser(description="Agente Estoque e Compras")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("saldo")
    sub.add_parser("repor")
    sub.add_parser("cotacoes")
    e = sub.add_parser("entrada")
    e.add_argument("--produto", required=True)
    e.add_argument("--qtd", type=float, required=True)
    e.add_argument("--custo", required=True, help="custo unitário em reais")
    e.add_argument("--fornecedor")
    s = sub.add_parser("saida")
    s.add_argument("--produto", required=True)
    s.add_argument("--qtd", type=float, required=True)
    q = sub.add_parser("cotacao")
    q.add_argument("--produto", required=True)
    q.add_argument("--fornecedor", required=True)
    q.add_argument("--preco", required=True)
    for sp in (e, s, q):
        sp.add_argument("--confirmar", action="store_true", help="grava de fato (só após aprovação)")
    a = p.parse_args()

    try:
        if a.cmd == "saldo":
            for r in saldo():
                print(f"{r['nome']:<25} {r['saldo']:>8.2f} {r['unidade']:<4} custo médio {reais(r['custo_medio_centavos'])}")
        elif a.cmd == "repor":
            itens = itens_para_repor()
            print("Nada para repor." if not itens else "\n".join(
                f"{r['nome']}: {r['saldo']:.2f} {r['unidade']} (mínimo {r['estoque_minimo']:.2f})" for r in itens))
        elif a.cmd == "cotacoes":
            for r in melhores_cotacoes():
                print(f"{r['produto']:<25} {r['fornecedor']:<22} {reais(r['preco_centavos'])}")
        else:
            if a.cmd == "entrada":
                res = registrar_entrada(a.produto, a.qtd, _centavos(a.custo), a.fornecedor, a.confirmar)
            elif a.cmd == "saida":
                res = registrar_saida(a.produto, a.qtd, a.confirmar)
            else:
                res = registrar_cotacao(a.produto, a.fornecedor, _centavos(a.preco), a.confirmar)
            print(("GRAVADO" if res["gravado"] else "PRÉVIA (nada gravado)"), res["previa"])
    except ErroEstoque as err:
        sys.exit(f"Erro: {err}")


if __name__ == "__main__":
    main()
