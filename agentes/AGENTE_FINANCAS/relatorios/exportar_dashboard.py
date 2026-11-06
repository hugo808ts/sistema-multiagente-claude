"""Gera os arquivos do Painel Financeiro (JSON) a partir do financas.db.

Uso:  python3 relatorios/exportar_dashboard.py '{"TICKER11": [10.00, "AAAA-MM-DD"], ...}'
      (cotação de cada ativo e a data dela; pesquisar na hora)
Saída: dados/financas/relatorios/dashboard/{contas,investimentos,cartao,movimentacoes}.json
"""
import sys, os, json, datetime, zoneinfo
PASTA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PASTA)
from db import conectar, DADOS

cot = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
c = conectar()
r = lambda cent: round((cent or 0) / 100, 2)
out = os.path.join(DADOS, "relatorios", "dashboard"); os.makedirs(out, exist_ok=True)
agora = datetime.datetime.now(zoneinfo.ZoneInfo("America/Sao_Paulo")).isoformat(timespec="minutes")

contas = [{"conta": x["nome"], "instituicao": x["instituicao"], "tipo": x["tipo"], "saldo": r(x["saldo_centavos"])}
          for x in c.execute("select * from v_saldo_contas where tipo <> 'corretora' order by saldo_centavos desc")]

inv = []
for x in c.execute("select * from v_posicao_invest order by codigo"):
    p, d = cot.get(x["codigo"], [None, None])
    inv.append({"ativo": x["codigo"], "classe": x["classe"].upper(), "onde": x["onde"], "cotas": x["quantidade"],
                "cotacao": p, "data_cotacao": d, "valor": round(p * x["quantidade"], 2) if p else None})

cart = []
for x in c.execute("select k.*, v.usado_centavos, v.disponivel_centavos from cartoes k join v_limite_cartoes v on v.cartao_id=k.id"):
    fat = c.execute("select fatura_mes, total_centavos from v_faturas where cartao=? and fatura_mes>=? order by fatura_mes limit 1",
                    (x["nome"], datetime.date.today().strftime("%Y-%m"))).fetchone()
    cart.append({"cartao": x["nome"], "limite": r(x["limite_centavos"]), "usado": r(x["usado_centavos"]),
                 "disponivel": r(x["disponivel_centavos"]), "meta": r(x["meta_mensal_centavos"]),
                 "fatura_atual": r(fat["total_centavos"]) if fat else 0, "fatura_mes": fat["fatura_mes"] if fat else None,
                 "fechamento": x["dia_fechamento"], "vencimento": x["dia_vencimento"]})

movs = [{"id": x["id"], "data": x["data"], "descricao": x["descricao"], "valor": r(x["valor_centavos"]), "tipo": x["tipo"],
         "categoria": x["categoria"] or "—", "onde": x["onde"] or "—"}
        for x in c.execute("""select m.id, m.data, m.descricao, m.valor_centavos, m.tipo,
               coalesce(p.nome, cat.nome) categoria, coalesce(k.nome, co.nome) onde
               from movimentacoes m left join categorias cat on cat.id=m.categoria_id left join categorias p on p.id=cat.pai_id
               left join contas co on co.id=m.conta_id left join cartoes k on k.id=m.cartao_id
               order by m.data desc, m.id desc""")]

for nome, rows in [("contas", contas), ("investimentos", inv), ("cartao", cart), ("movimentacoes", movs)]:
    json.dump({"gerado_em": agora, "rows": rows}, open(os.path.join(out, nome + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("ok", agora, {k: len(v) for k, v in [("contas", contas), ("inv", inv), ("cartao", cart), ("movs", movs)]})
