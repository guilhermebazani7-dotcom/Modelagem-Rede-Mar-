# T1 — Modelagem Informacional · Trilha C
## Da Planilha Caótica ao Modelo Relacional em 3FN: inteligência de preços para a Rede Maré Combustíveis

**Aluno:** Guilherme Bazani Demuner · **FUCAPE Business School** · Ciência de Dados para Negócios

A Rede Maré, uma rede fictícia de 5 postos de bandeira branca na Grande Vitória, construída sobre dados reais e anonimizados da ANP, acompanha os preços da concorrência numa planilha única e desnormalizada. Este projeto diagnostica as anomalias dessa planilha, normaliza os dados até a 3FN, implementa o modelo em PostgreSQL com integridade referencial estrita, cria VIEWs analíticas para a decisão de preço e estima o ROI da solução.

---

## Estrutura

```
├── README.md
├── requirements.txt
├── relatorio/
│   └── Relatorio_T1_Guilherme_Bazani_Demuner.pdf   <- relatório executivo
├── modelagem/
│   ├── normalizacao.md      <- dependências funcionais e 1FN → 2FN → 3FN
│   └── der.md               <- DER em Mermaid.js (renderiza no GitHub)
├── dados/
│   ├── 01_recorte_anp.py            <- recorta a base nacional da ANP para uma UF
│   ├── 02_gerador_planilha_caotica.py <- gera a "planilha monstro" (seed fixa)
│   ├── 03_normalizar.py             <- limpeza + 1FN + 2FN + 3FN
│   ├── anp_recorte_ES.csv           <- base real (ANP, ES, 1º sem/2026)
│   ├── planilha_caotica.csv         <- tabela universal desnormalizada
│   ├── metricas_baseline.json       <- KPIs do cenário "antes"
│   └── normalizado/                 <- tabelas de cada etapa (0_original ... 3fn)
└── sql/
    ├── 01_ddl.sql       <- tabelas + PK, FK, UNIQUE, CHECK
    ├── 02_carga.sql     <- carga das tabelas 3FN
    ├── 03_views.sql     <- 4 VIEWs analíticas com JOINs
    ├── 04_testes.sql    <- 19 testes automatizados (anomalias e constraints)
    └── 05_roi.sql       <- estimativa de impacto financeiro
```

---

## Como executar (Windows)

### Pré-requisitos

1. **Python 3.10+:** baixe em [python.org](https://www.python.org/downloads/) e marque a opção *"Add Python to PATH"* na instalação.
2. **PostgreSQL 14+:** baixe o instalador em [postgresql.org/download/windows](https://www.postgresql.org/download/windows/). Durante a instalação:
   - defina e **anote a senha** do usuário `postgres`;
   - mantenha a porta padrão `5432`;
   - mantenha marcado o componente *Command Line Tools*, que instala o `psql`.
3. **Adicionar o `psql` ao PATH** (uma vez só): abra o *PowerShell* e rode o comando abaixo, ajustando o número da versão (`17`) se for diferente:
   ```powershell
   setx PATH "$env:PATH;C:\Program Files\PostgreSQL\17\bin"
   ```
   Feche e reabra o PowerShell. Teste com `psql --version`.

### Passo 1 — Instalar a dependência Python

No PowerShell, **dentro da pasta do projeto**:

```powershell
pip install -r requirements.txt
```

### Passo 2 — (Opcional) Regerar os dados

As bases já estão prontas em `dados/`. Para reproduzir tudo do zero:

```powershell
cd dados
# (opcional) recortar a base nacional baixada da ANP: ca-2026-01.csv
python 01_recorte_anp.py ca-2026-01.csv ES
python 02_gerador_planilha_caotica.py anp_recorte_ES.csv
python 03_normalizar.py planilha_caotica.csv anp_recorte_ES.csv
cd ..
```

O script `03_normalizar.py` imprime o tamanho das tabelas em cada forma normal e valida a decomposição do endereço contra a base original da ANP (158/158).

### Passo 3 — Criar o banco

```powershell
$env:PGUSER = "postgres"
$env:PGPASSWORD = "SUA_SENHA_AQUI"
psql -c "CREATE DATABASE rede_mare;"
```

### Passo 4 — Rodar os scripts SQL (na raiz do projeto, nesta ordem)

```powershell
psql -d rede_mare -f sql/01_ddl.sql
psql -d rede_mare -f sql/02_carga.sql
psql -d rede_mare -f sql/03_views.sql
psql -d rede_mare -f sql/04_testes.sql
psql -d rede_mare -f sql/05_roi.sql
```

**Resultado esperado:**

| Script | O que deve aparecer |
|---|---|
| `02_carga.sql` | Contagem de linhas por tabela (ex.: `coleta` = 2176, `item_coleta` = 7717) |
| `04_testes.sql` | Tabela com 19 testes e o resumo `passou = 19 · falhou = 0` |
| `05_roi.sql` | Margem na mesa por posto/produto e os cenários de ROI (base ≈ R$ 29 mil/mês) |

Os testes rodam dentro de uma transação com `ROLLBACK`, então podem ser executados quantas vezes quiser sem alterar o banco. O `01_ddl.sql` é idempotente: recria o schema do zero a cada execução.

### Consultando as VIEWs

```powershell
psql -d rede_mare
```
```sql
SET search_path TO rede_mare;
SELECT * FROM vw_painel_rede_mare ORDER BY posto, produto;
SELECT * FROM vw_posicionamento_concorrencia WHERE posto = 'MARE HORTO' LIMIT 10;
```

---

## Principais resultados

- **Normalização:** 1 tabela universal (2.186 × 20) → 14 tabelas em 3FN; células cadastrais repetidas: 16.224 → 0.
- **Integridade:** 19/19 testes aprovados. As três anomalias foram eliminadas, e 14 regras de CHECK, PK, UNIQUE e FK rejeitam dados inválidos.
- **Negócio:** os postos da rede vendem abaixo dos concorrentes diretos com frequência (ex.: etanol do Horto R$ 0,20/L abaixo em 100% das semanas). O ganho estimado é de R$ 14,5 mil a R$ 58 mil/mês, com payback inferior a um mês.

## Dados reais e simulados

- **Real (ANP):** postos concorrentes, endereços, bandeiras, datas e preços de venda.
- **Simulado (seed fixa, documentado em `02_gerador_planilha_caotica.py`):** colunas internas da empresa (gerente, telefones, serviços, concorrentes diretos) e sujeiras de digitação.
- **Anonimizado:** os 5 postos da Rede Maré são postos reais de bandeira branca, com CNPJ e razão social fictícios.

**Fonte dos dados:** ANP — Série Histórica de Preços de Combustíveis e de GLP (gov.br/anp, dados abertos).
