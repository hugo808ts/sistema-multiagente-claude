# Orquestrador Multiagente com Claude

![testes](https://github.com/hugo808ts/orquestrador-multiagente-claude/actions/workflows/testes.yml/badge.svg)

Sistema de agentes de IA para a operação de uma empresa de refeições: um **Coordenador** recebe o pedido em linguagem natural, distribui o trabalho entre agentes especialistas (Atendimento, Estoque e Compras, Financeiro e GitHub) e devolve uma resposta única. Nenhuma gravação acontece sem aprovação humana.

> Os dados de demonstração são fictícios (empresa "Cozinha Exemplo").

## Exemplo

> **Usuário:** chegou a NF do Atacado Alfa: 10 pacotes de arroz 5kg a R$ 23,50, vence dia 10. E o que falta comprar pra produção de amanhã?

1. O Coordenador identifica três áreas: **Estoque** (entrada da nota), **Financeiro** (conta a pagar) e **Atendimento** (produção de amanhã).
2. Estoque e Financeiro montam as prévias **em paralelo**. Atendimento soma os pedidos do dia e passa o total para o Estoque, que cruza com o saldo e com as cotações.
3. O usuário recebe uma resposta só: as duas prévias para aprovar, a lista de compra com o fornecedor mais barato e o alerta de itens abaixo do mínimo.
4. Depois do OK, cada agente grava no próprio banco, com backup antes.

## Funcionalidades

**Coordenador**
- Roteamento por intenção, com delegação em paralelo ou em sequência quando uma área depende da outra
- Aprovação humana centralizada: uma confirmação para o pedido inteiro
- Alertas no topo (conta vencida, item abaixo do mínimo)

**Agentes**

| Agente | O que faz | Técnica |
|---|---|---|
| Atendimento | Transforma mensagem de cliente em pedido estruturado e soma a produção do dia | Extração para JSON pelo modelo + validação em Python |
| Estoque e Compras | Saldo, entradas e saídas, reposição, melhor cotação por fornecedor | SQLite com views de saldo, custo médio ponderado e reposição |
| Financeiro | Contas a pagar e a receber, baixas, fluxo mensal, despesas por centro de custo | SQLite com views de fluxo de caixa |
| GitHub | README, commits, push e releases | API REST do GitHub + varredura de segredos antes do push |

## Tecnologias
- **Claude Code**: subagentes e instruções por projeto (`CLAUDE.md`)
- **Python 3.10+** (só biblioteca padrão) e **SQLite**
- **SQL**: constraints, chaves estrangeiras e views para as regras de negócio
- **API REST do GitHub**
- **GitHub Actions**: testes automatizados a cada push

## Como executar

Requer Python 3.10+ e, para usar os agentes, o [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) (plano pago do Claude).

```bash
git clone https://github.com/hugo808ts/orquestrador-multiagente-claude.git
cd orquestrador-multiagente-claude

python scripts/iniciar_dados.py --demo     # cria os bancos com dados fictícios
python -m unittest discover -s tests       # roda os testes

claude                                     # abre o Coordenador
```

As ferramentas também funcionam direto no terminal, sem IA:

```bash
python agentes/AGENTE_ESTOQUE/estoque.py repor
python agentes/AGENTE_ESTOQUE/estoque.py saida --produto "Arroz 5kg" --qtd 3      # só prévia
python agentes/AGENTE_ATENDIMENTO/atendimento.py validar --json dados_exemplo/pedido_exemplo.json
python agentes/AGENTE_FINANCEIRO/financeiro.py em-aberto --dias 7
```

## Arquitetura

O modelo interpreta o pedido; o código garante as regras. Cada agente só acessa o banco pelos próprios scripts, que validam os dados e, nas escritas, mostram uma **prévia** e só gravam com `--confirmar`. Assim a aprovação humana fica no código, não depende apenas do prompt.

Diagramas, estrutura de pastas e decisões de projeto: [docs/ARQUITETURA.md](docs/ARQUITETURA.md).

## Autor
Hugo Vieira, estudante de Sistemas de Informação na UFU. [GitHub](https://github.com/hugo808ts) · [LinkedIn](https://www.linkedin.com/in/hugo-vieira06)
