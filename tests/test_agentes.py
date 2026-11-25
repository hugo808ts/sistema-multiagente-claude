"""Testes das ferramentas dos agentes. Rodar: python -m unittest discover -s tests"""
import datetime
import importlib.util
import os
import sys
import tempfile
import unittest

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, RAIZ)


def carregar(caminho, nome):
    spec = importlib.util.spec_from_file_location(nome, os.path.join(RAIZ, caminho))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


estoque = carregar("agentes/AGENTE_ESTOQUE/estoque.py", "estoque")
atendimento = carregar("agentes/AGENTE_ATENDIMENTO/atendimento.py", "atendimento")
financeiro = carregar("agentes/AGENTE_FINANCEIRO/financeiro.py", "financeiro")
iniciar_dados = carregar("scripts/iniciar_dados.py", "iniciar_dados")

AMANHA = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()


class BaseTeste(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["ORQ_DADOS"] = self.tmp.name
        for agente, schema in iniciar_dados.AGENTES.items():
            iniciar_dados.iniciar(agente, os.path.join(RAIZ, schema))
        iniciar_dados.carregar_demo()

    def tearDown(self):
        os.environ.pop("ORQ_DADOS", None)
        self.tmp.cleanup()


class TestEstoque(BaseTeste):
    def _saldo(self, nome):
        return next(r for r in estoque.saldo() if r["nome"] == nome)

    def test_saldo_e_custo_medio(self):
        arroz = self._saldo("Arroz 5kg")
        self.assertEqual(arroz["saldo"], 12)                    # 20 + 10 - 18
        self.assertEqual(arroz["custo_medio_centavos"], 2443)   # (20*2490 + 10*2350) / 30

    def test_previa_nao_grava(self):
        res = estoque.registrar_saida("Arroz 5kg", 2)
        self.assertFalse(res["gravado"])
        self.assertEqual(self._saldo("Arroz 5kg")["saldo"], 12)

    def test_saida_confirmada_grava(self):
        estoque.registrar_saida("Arroz 5kg", 2, confirmar=True)
        self.assertEqual(self._saldo("Arroz 5kg")["saldo"], 10)

    def test_saida_maior_que_saldo_falha(self):
        with self.assertRaises(estoque.ErroEstoque):
            estoque.registrar_saida("Arroz 5kg", 999, confirmar=True)

    def test_reposicao_e_cotacao(self):
        nomes = {r["nome"] for r in estoque.itens_para_repor()}
        self.assertIn("Óleo de soja 900ml", nomes)              # 10 <= mínimo 12
        self.assertNotIn("Frango congelado", nomes)             # 35 > mínimo 30
        melhor = {r["produto"]: r for r in estoque.melhores_cotacoes()}
        self.assertEqual(melhor["Arroz 5kg"]["fornecedor"], "Distribuidora Beta")

    def test_backup_antes_de_gravar(self):
        estoque.registrar_entrada("Feijão 1kg", 5, 800, "Atacado Alfa", confirmar=True)
        pasta = os.path.join(self.tmp.name, "estoque", "backups")
        self.assertEqual(len(os.listdir(pasta)), 1)


class TestAtendimento(BaseTeste):
    def pedido(self, **extra):
        p = {"cliente": "Unidade Norte", "data_entrega": AMANHA, "refeicao": "jantar",
             "itens": [{"item": "Marmita executiva", "quantidade": 25}]}
        p.update(extra)
        return p

    def test_pedido_valido(self):
        self.assertEqual(atendimento.validar_pedido(self.pedido()), [])

    def test_pedido_invalido(self):
        erros = atendimento.validar_pedido(self.pedido(refeicao="ceia", itens=[{"item": "X", "quantidade": 0}]))
        self.assertTrue(any("refeição" in e for e in erros))
        self.assertTrue(any("quantidade" in e for e in erros))

    def test_cliente_desconhecido(self):
        with self.assertRaises(atendimento.ErroPedido):
            atendimento.registrar_pedido(self.pedido(cliente="Fulano"), confirmar=True)

    def test_registro_entra_na_producao(self):
        atendimento.registrar_pedido(self.pedido(refeicao="almoco"), confirmar=True)
        prod = {r["item"]: r["total"] for r in atendimento.producao_do_dia(AMANHA)}
        self.assertEqual(prod["Marmita executiva"], 65)          # 40 da demo + 25

    def test_cancelado_sai_da_producao(self):
        atendimento.cancelar(1, confirmar=True)
        self.assertEqual(atendimento.producao_do_dia(AMANHA), [])


class TestFinanceiro(BaseTeste):
    def test_em_aberto_marca_vencida(self):
        abertas = {r["descricao"]: r for r in financeiro.em_aberto()}
        self.assertEqual(abertas["Frete semanal"]["vencida"], 1)
        self.assertEqual(abertas["NF 2210 - frango"]["vencida"], 0)

    def test_baixa_muda_fluxo(self):
        conta = next(r for r in financeiro.em_aberto() if r["descricao"] == "Frete semanal")
        hoje = datetime.date.today().isoformat()
        financeiro.baixar(conta["id"], hoje, confirmar=True)
        with self.assertRaises(financeiro.ErroFinanceiro):
            financeiro.baixar(conta["id"], hoje, confirmar=True)  # não baixa duas vezes
        self.assertNotIn(conta["id"], [r["id"] for r in financeiro.em_aberto()])

    def test_lancamento_invalido(self):
        with self.assertRaises(financeiro.ErroFinanceiro):
            financeiro.lancar("pagar", "X", "Y", "insumos", 0, AMANHA, confirmar=True)


if __name__ == "__main__":
    unittest.main()
