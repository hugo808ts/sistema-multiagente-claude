"""Conexão padrão com o financas.db.
A pasta fica no OneDrive, onde o travamento normal do SQLite falha.
Por isso: nolock=1 + journal em memória + backup antes de gravar.

Uso:
    from db import conectar, backup
    backup()                 # antes de qualquer escrita
    c = conectar()
    c.execute("...")
    c.commit()
"""
import os, shutil, sqlite3, datetime

PASTA = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.abspath(os.path.join(PASTA, "..", ".."))
# Dados ficam fora do Git, em <raiz>/dados/financas (pode ser trocado pela variável de ambiente)
DADOS = os.environ.get("AGENTES_DADOS_FINANCAS", os.path.join(RAIZ, "dados", "financas"))
DB = os.path.join(DADOS, "financas.db")
BACKUPS = os.path.join(DADOS, "backups")
MAX_BACKUPS = 15

def conectar():
    os.makedirs(DADOS, exist_ok=True)
    c = sqlite3.connect(f"file:{DB}?nolock=1", uri=True)
    c.execute("PRAGMA journal_mode=MEMORY")
    c.execute("PRAGMA foreign_keys=ON")
    c.row_factory = sqlite3.Row
    return c

def backup():
    os.makedirs(BACKUPS, exist_ok=True)
    nome = datetime.datetime.now().strftime("financas_%Y-%m-%d_%H%M%S.db")
    shutil.copyfile(DB, os.path.join(BACKUPS, nome))
    return nome
