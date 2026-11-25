"""Acesso padrão aos bancos SQLite dos agentes.

Cada agente tem o próprio banco em <dados>/<agente>/<agente>.db.
A pasta de dados fica fora do Git e pode ser trocada pela variável
de ambiente ORQ_DADOS (usado nos testes).

Uso:
    from nucleo.db import conectar, backup
    backup("estoque")          # sempre antes de gravar
    c = conectar("estoque")
"""
import datetime
import os
import shutil
import sqlite3

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MAX_BACKUPS = 15


def pasta_dados(agente: str) -> str:
    base = os.environ.get("ORQ_DADOS", os.path.join(RAIZ, "dados"))
    return os.path.join(base, agente)


def caminho_banco(agente: str) -> str:
    return os.path.join(pasta_dados(agente), f"{agente}.db")


class Conexao(sqlite3.Connection):
    """Conexão que faz commit/rollback e fecha ao sair do bloco `with`."""

    def __exit__(self, *exc):
        resultado = super().__exit__(*exc)
        self.close()
        return resultado


def conectar(agente: str) -> sqlite3.Connection:
    os.makedirs(pasta_dados(agente), exist_ok=True)
    c = sqlite3.connect(caminho_banco(agente), factory=Conexao)
    c.execute("PRAGMA foreign_keys=ON")
    c.row_factory = sqlite3.Row
    return c


def iniciar(agente: str, schema: str) -> None:
    """Cria as tabelas do agente a partir do schema.sql (idempotente)."""
    with open(schema, encoding="utf-8") as f:
        sql = f.read()
    c = conectar(agente)
    c.executescript(sql)
    c.commit()
    c.close()


def backup(agente: str) -> str | None:
    """Copia o banco para backups/ e mantém só os MAX_BACKUPS mais recentes."""
    banco = caminho_banco(agente)
    if not os.path.exists(banco):
        return None
    pasta = os.path.join(pasta_dados(agente), "backups")
    os.makedirs(pasta, exist_ok=True)
    nome = datetime.datetime.now().strftime(f"{agente}_%Y-%m-%d_%H%M%S_%f.db")
    shutil.copyfile(banco, os.path.join(pasta, nome))
    antigos = sorted(os.listdir(pasta))[:-MAX_BACKUPS]
    for arq in antigos:
        os.remove(os.path.join(pasta, arq))
    return nome


def reais(centavos: int | None) -> str:
    if centavos is None:
        return "-"
    return f"R$ {centavos / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
