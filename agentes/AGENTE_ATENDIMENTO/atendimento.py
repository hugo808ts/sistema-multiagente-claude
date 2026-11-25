"""Ferramentas do Agente Atendimento.

O modelo lê a mensagem do cliente e monta o pedido em JSON:
    {"cliente": "Unidade Centro", "data_entrega": "2026-12-01", "refeicao": "almoco",
     "itens": [{"item": "Marmita executiva", "quantidade": 40}],
     "mensagem": "texto original"}
Este script valida o JSON e só grava com --confirmar.

    python atendimento.py validar  --json pedido.json
    python atendimento.py registrar --json pedido.json [--confirmar]
    python atendimento.py pedidos  [--data 2026-12-01]
    python atendimento.py producao --data 2026-12-01
    python atendimento.py cancelar --id 3 [--confirmar]
"""
import argparse
import datetime
import json
import os
import sys

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, RAIZ)
from nucleo.db import backup, conectar, iniciar  # noqa: E402

AGENTE = "atendimento"
SCHEMA = os.path.join(os.path.dirname(__file__), "schema.sql")
REFEICOES = {"cafe", "almoco", "jantar"}


class ErroPedido(Exception):
    pass


def _db():
    iniciar(AGENTE, SCHEMA)
    return conectar(AGENTE)


def validar_pedido(p: dict) -> list[str]:
    """Devolve a lista de problemas do pedido (vazia = pedido válido)."""
    erros = []
    for campo in ("cliente", "data_entrega", "refeicao", "itens"):
        if not p.get(campo):
            erros.append(f"campo obrigatório ausente: {campo}")
    if p.get("refeicao") and p["refeicao"] not in REFEICOES:
        erros.append(f"refeição inválida: {p['refeicao']} (use {', '.join(sorted(REFEICOES))})")
    if p.get("data_entrega"):
        try:
            if datetime.date.fromisoformat(p["data_entrega"]) < datetime.date.today():
                erros.append("data de entrega no passado")
        except ValueError:
            erros.append("data_entrega fora do formato AAAA-MM-DD")
    for i, item in enumerate(p.get("itens") or [], 1):
        if not item.get("item"):
            erros.append(f"item {i} sem nome")
        q = item.get("quantidade")
        if not isinstance(q, int) or q <= 0:
            erros.append(f"item {i} com quantidade inválida: {q}")
    if p.get("cliente") and not erros:
        with _db() as c:
            if not c.execute("SELECT 1 FROM clientes WHERE nome = ?", (p["cliente"],)).fetchone():
                erros.append(f"cliente não cadastrado: {p['cliente']}")
    return erros


def registrar_pedido(p: dict, confirmar=False):
    erros = validar_pedido(p)
    if erros:
        raise ErroPedido("; ".join(erros))
    if not confirmar:
        return {"previa": p, "gravado": False}
    backup(AGENTE)
    with _db() as c:
        cid = c.execute("SELECT id FROM clientes WHERE nome = ?", (p["cliente"],)).fetchone()["id"]
        cur = c.execute("INSERT INTO pedidos (cliente_id, data_entrega, refeicao, mensagem) VALUES (?, ?, ?, ?)",
                        (cid, p["data_entrega"], p["refeicao"], p.get("mensagem")))
        c.executemany("INSERT INTO itens_pedido (pedido_id, item, quantidade) VALUES (?, ?, ?)",
                      [(cur.lastrowid, i["item"], i["quantidade"]) for i in p["itens"]])
        return {"previa": p, "gravado": True, "id": cur.lastrowid}


def listar_pedidos(data=None):
    sql = ("SELECT p.id, c.nome AS cliente, p.data_entrega, p.refeicao, p.status,"
           " GROUP_CONCAT(i.item || ' x' || i.quantidade, ', ') AS itens"
           " FROM pedidos p JOIN clientes c ON c.id = p.cliente_id"
           " LEFT JOIN itens_pedido i ON i.pedido_id = p.id")
    args = ()
    if data:
        sql += " WHERE p.data_entrega = ?"
        args = (data,)
    sql += " GROUP BY p.id ORDER BY p.data_entrega, p.id"
    with _db() as c:
        return [dict(r) for r in c.execute(sql, args)]


def producao_do_dia(data):
    with _db() as c:
        return [dict(r) for r in c.execute(
            "SELECT refeicao, item, total FROM vw_producao_dia WHERE data_entrega = ? ORDER BY refeicao, item",
            (data,))]


def cancelar(pedido_id, confirmar=False):
    with _db() as c:
        linha = c.execute("SELECT status FROM pedidos WHERE id = ?", (pedido_id,)).fetchone()
        if not linha:
            raise ErroPedido(f"pedido {pedido_id} não existe")
        if linha["status"] != "confirmado":
            raise ErroPedido(f"pedido {pedido_id} está '{linha['status']}', não pode ser cancelado")
        if not confirmar:
            return {"previa": {"acao": "cancelar", "pedido": pedido_id}, "gravado": False}
        backup(AGENTE)
        c.execute("UPDATE pedidos SET status = 'cancelado' WHERE id = ?", (pedido_id,))
        return {"previa": {"acao": "cancelar", "pedido": pedido_id}, "gravado": True}


def main():
    p = argparse.ArgumentParser(description="Agente Atendimento")
    sub = p.add_subparsers(dest="cmd", required=True)
    for nome in ("validar", "registrar"):
        sp = sub.add_parser(nome)
        sp.add_argument("--json", required=True, help="arquivo JSON do pedido")
        if nome == "registrar":
            sp.add_argument("--confirmar", action="store_true")
    sub.add_parser("pedidos").add_argument("--data")
    sub.add_parser("producao").add_argument("--data", required=True)
    cc = sub.add_parser("cancelar")
    cc.add_argument("--id", type=int, required=True)
    cc.add_argument("--confirmar", action="store_true")
    a = p.parse_args()

    try:
        if a.cmd in ("validar", "registrar"):
            with open(a.json, encoding="utf-8") as f:
                pedido = json.load(f)
            if a.cmd == "validar":
                erros = validar_pedido(pedido)
                print("Pedido válido." if not erros else "Problemas:\n- " + "\n- ".join(erros))
            else:
                res = registrar_pedido(pedido, a.confirmar)
                print(f"GRAVADO (pedido {res['id']})" if res["gravado"] else "PRÉVIA (nada gravado)",
                      json.dumps(pedido, ensure_ascii=False))
        elif a.cmd == "pedidos":
            for r in listar_pedidos(a.data):
                print(f"#{r['id']} {r['data_entrega']} {r['refeicao']:<7} {r['cliente']:<20} {r['status']:<10} {r['itens']}")
        elif a.cmd == "producao":
            for r in producao_do_dia(a.data):
                print(f"{r['refeicao']:<7} {r['item']:<25} {r['total']}")
        else:
            res = cancelar(a.id, a.confirmar)
            print("GRAVADO" if res["gravado"] else "PRÉVIA (nada gravado)", res["previa"])
    except ErroPedido as err:
        sys.exit(f"Erro: {err}")


if __name__ == "__main__":
    main()
