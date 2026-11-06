"""Cria o financas.db vazio a partir do schema.sql.
Uso: python iniciar_banco.py
"""
import os, sys
PASTA = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PASTA)
from db import conectar, DB

if os.path.exists(DB):
    sys.exit("financas.db já existe — nada a fazer.")
c = conectar()
c.executescript(open(os.path.join(PASTA, "schema.sql"), encoding="utf-8").read())
c.commit()
print("Banco criado:", DB)
