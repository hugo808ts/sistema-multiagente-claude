"""Ferramentas do Agente Financeiro (contas a pagar e a receber).

    python financeiro.py em-aberto [--dias 7]
    python financeiro.py fluxo
    python financeiro.py centros --mes 2026-11
    python financeiro.py lancar --tipo pagar --descricao "NF 123" --parte "Atacado Alfa" \
        --centro insumos --valor 1250.00 --vencimento 2026-12-05 [--confirmar]
    python financeiro.py baixar --id 4 [--data 2026-11-25] [--confirmar]
"""
import argparse
import datetime
import os
import sys

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, RAIZ)
from nucleo.db import backup, conectar, iniciar, reais  # noqa: E402

AGENTE = "financeiro"
SCHEMA = os.path.join(os.path.dirname(__file__), "schema.sql")


class ErroFinanceiro(Exception):
    pass


def _db():
    iniciar(AGENTE, SCHEMA)
    return conectar(AGENTE)


def em_aberto(dias=None):
    """Contas em aberto. Com `dias`, só as que vencem até hoje + dias (inclui vencidas)."""
    sql, args = "SELECT * FROM vw_em_aberto", ()
    if dias is not None:
        sql += " WHERE vencimento <= date('now', ?)"
        args = (f"+{int(dias)} day",)
    with _db() as c:
        return [dict(r) for r in c.execute(sql + " ORDER BY vencimento", args)]


def fluxo_mensal():
    with _db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM vw_fluxo_mensal ORDER BY mes")]


def despesas_por_centro(mes):
    with _db() as c:
        return [dict(r) for r in c.execute(
            "SELECT centro_custo, total FROM vw_despesas_centro WHERE mes = ? ORDER BY total DESC", (mes,))]


def lancar(tipo, descricao, parte, centro, valor_centavos, vencimento, confirmar=False):
    if tipo not in ("pagar", "receber"):
        raise ErroFinanceiro("tipo deve ser 'pagar' ou 'receber'")
    if valor_centavos <= 0:
        raise ErroFinanceiro("valor deve ser maior que zero")
    try:
        datetime.date.fromisoformat(vencimento)
    except ValueError:
        raise ErroFinanceiro("vencimento fora do formato AAAA-MM-DD")
    previa = {"acao": "lancar", "tipo": tipo, "descricao": descricao, "parte": parte,
              "centro_custo": centro, "valor": reais(valor_centavos), "vencimento": vencimento}
    if not confirmar:
        return {"previa": previa, "gravado": False}
    backup(AGENTE)
    with _db() as c:
        cur = c.execute("INSERT INTO contas (tipo, descricao, parte, centro_custo, valor_centavos, vencimento)"
                        " VALUES (?, ?, ?, ?, ?, ?)", (tipo, descricao, parte, centro, valor_centavos, vencimento))
        return {"previa": previa, "gravado": True, "id": cur.lastrowid}


def baixar(conta_id, data=None, confirmar=False):
    data = data or datetime.date.today().isoformat()
    with _db() as c:
        conta = c.execute("SELECT * FROM contas WHERE id = ?", (conta_id,)).fetchone()
        if not conta:
            raise ErroFinanceiro(f"conta {conta_id} não existe")
        if conta["pago_em"]:
            raise ErroFinanceiro(f"conta {conta_id} já foi baixada em {conta['pago_em']}")
        previa = {"acao": "baixar", "conta": conta_id, "descricao": conta["descricao"],
                  "valor": reais(conta["valor_centavos"]), "pago_em": data}
        if not confirmar:
            return {"previa": previa, "gravado": False}
        backup(AGENTE)
        c.execute("UPDATE contas SET pago_em = ? WHERE id = ?", (data, conta_id))
        return {"previa": previa, "gravado": True}


def main():
    p = argparse.ArgumentParser(description="Agente Financeiro")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("em-aberto").add_argument("--dias", type=int)
    sub.add_parser("fluxo")
    sub.add_parser("centros").add_argument("--mes", required=True)
    l = sub.add_parser("lancar")
    for arg in ("tipo", "descricao", "parte", "centro", "valor", "vencimento"):
        l.add_argument(f"--{arg}", required=True)
    b = sub.add_parser("baixar")
    b.add_argument("--id", type=int, required=True)
    b.add_argument("--data")
    for sp in (l, b):
        sp.add_argument("--confirmar", action="store_true")
    a = p.parse_args()

    try:
        if a.cmd == "em-aberto":
            for r in em_aberto(a.dias):
                alerta = " VENCIDA" if r["vencida"] else ""
                print(f"#{r['id']} {r['vencimento']} {r['tipo']:<7} {reais(r['valor_centavos']):>13} {r['parte']} - {r['descricao']}{alerta}")
        elif a.cmd == "fluxo":
            for r in fluxo_mensal():
                print(f"{r['mes']}  entradas {reais(r['entradas'])}  saídas {reais(r['saidas'])}  saldo {reais(r['saldo'])}")
        elif a.cmd == "centros":
            for r in despesas_por_centro(a.mes):
                print(f"{r['centro_custo']:<15} {reais(r['total'])}")
        elif a.cmd == "lancar":
            valor = round(float(a.valor.replace(",", ".")) * 100)
            res = lancar(a.tipo, a.descricao, a.parte, a.centro, valor, a.vencimento, a.confirmar)
            print("GRAVADO" if res["gravado"] else "PRÉVIA (nada gravado)", res["previa"])
        else:
            res = baixar(a.id, a.data, a.confirmar)
            print("GRAVADO" if res["gravado"] else "PRÉVIA (nada gravado)", res["previa"])
    except ErroFinanceiro as err:
        sys.exit(f"Erro: {err}")


if __name__ == "__main__":
    main()
