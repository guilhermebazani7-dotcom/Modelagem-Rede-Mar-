# Normalização da Planilha de Pricing — Rede Maré Combustíveis

Este documento registra a aplicação metódica das três primeiras Formas Normais sobre a `planilha_caotica.csv`. Cada etapa é reproduzível com `python 03_normalizar.py planilha_caotica.csv anp_recorte_ES.csv`, que grava as tabelas intermediárias em `normalizado/<etapa>/`. Todos os números citados abaixo saem da execução desse script.

---

## 0. Ponto de partida: a tabela universal (forma não normalizada)

A planilha tem **2.186 linhas × 20 colunas** e mistura cinco contextos de negócio: coleta de preço, cadastro do posto, localização, catálogo de produtos e informações internas da Rede Maré. O analista identifica cada linha pelo par **(cnpj, data_coleta)**.

Exemplo real de uma linha (posto próprio de Cariacica, 07/01/2026):

| Coluna | Valor |
|---|---|
| cnpj | 11.222.333/0001-81 |
| razao_social / grupo_economico | REDE MARE COMBUSTIVEIS LTDA / REDE MARE |
| bandeira | BRANCA |
| endereco | AVENIDA MARIO GURGEL, 1092 - ITAQUARI |
| municipio / uf / regiao | CARIACICA / ES / SE |
| produtos | DIESEL, DIESEL S10, ETANOL, GASOLINA, GASOLINA ADITIVADA, GNV |
| precos | 5,90 / 5,97 / 4,65 / 6,19 / 6,19 / 4,09 |
| unidades | R$ / litro; R$ / litro; … ; R$ / m³ |
| servicos | Conveniencia, Troca de oleo, Caixa eletronico, Borracharia |
| gerente / telefones_gerente | Carlos Menezes / (27) 99811-2041 / (27) 3334-1100 |
| concorrentes_diretos | 00.580.488/0001-73 / 13.814.642/0001-76 / 15.226.314/0001-84 |

### Dependências funcionais levantadas

As regras de negócio abaixo foram confirmadas nos dados (ex.: a combinação cnpj + data + produto nunca se repete; cada produto tem uma única unidade de medida).

| # | Dependência funcional | Tipo (em relação à chave da 1FN) |
|---|---|---|
| DF1 | (cnpj, data_coleta, produto) → valor_venda | Total ✔ |
| DF2 | produto → unidade_medida | Parcial ✘ |
| DF3 | cnpj → razao_social, tipo_posto, logradouro, numero, complemento, bairro, cep, municipio, uf, regiao, grupo_economico, gerente | Parcial ✘ |
| DF4 | (cnpj, data_coleta) → bandeira, semana_ref, observacoes | Parcial ✘ |
| DF5 | municipio → uf → regiao | Transitiva ✘ |
| DF6 | cnpj → cnpj_raiz → grupo_economico | Transitiva ✘ |
| DF7 | gerente → telefones | Transitiva ✘ |
| DF8 | data_coleta → semana_ref | Transitiva (atributo derivado) ✘ |

---

## Etapa 0 — Limpeza de formato (pré-requisito, não é normalização)

Normalização resolve problemas de **estrutura**. Grafias divergentes são problemas de **conteúdo**. Sem limpá-las antes, "Vitória" e "VITORIA" virariam dois municípios diferentes na 3FN. A limpeza aplicada foi:

- remoção de 10 linhas duplicadas (2.186 → 2.176);
- CNPJ reduzido a 14 dígitos (remove o espaço inicial herdado da ANP e unifica máscaras);
- datas em dois formatos (dd/mm/aaaa e aaaa-mm-dd) convertidas para `DATE`;
- municípios em maiúsculas, sem acento, com abreviações expandidas ("V. VELHA" → "VILA VELHA");
- razão social canônica = grafia mais frequente por CNPJ (79 postos tinham mais de uma grafia);
- unidade "R$/l" padronizada para "R$ / litro".

> **Erro encontrado pelo próprio banco.** Na primeira versão, as datas eram convertidas com detecção automática de formato. Nas 59 linhas em formato ISO, 26 tiveram dia e mês invertidos (2026-02-11 virou 2026-11-02), sem nenhum aviso. Só uma delas foi detectada, porque caiu no futuro e violou o `CHECK` de `coleta.data_coleta` durante a carga. As outras 25 teriam entrado erradas em silêncio. A correção foi usar formatos explícitos e abortar a execução diante de qualquer data desconhecida. O episódio mostra o papel das constraints como última linha de defesa e também seus limites: elas só barram o que é impossível, não o que é plausível e errado.

---

## Etapa 1 — Primeira Forma Normal (1FN)

**Regra:** todos os atributos devem ser atômicos, sem grupos repetitivos nem atributos multivalorados.

### Violações encontradas

1. **Grupo repetitivo:** `produtos`, `precos` e `unidades` são três listas paralelas. O 3º preço pertence ao 3º produto — uma regra que só existe na cabeça do analista.
2. **Atributos multivalorados independentes:** `servicos`, `telefones_gerente` e `concorrentes_diretos`.
3. **Atributo composto:** `endereco` junta logradouro, número, complemento e bairro numa string.

### Decisão de projeto

A saída ingênua seria "achatar" tudo, gerando uma linha para cada combinação. Como os multivalorados são **independentes entre si**, isso produziria um produto cartesiano: **23.465 linhas** (produtos × serviços × telefones × concorrentes), com fatos falsos do tipo "o preço do etanol está associado ao telefone fixo do gerente".

Por isso, adotou-se o procedimento recomendado para atributos multivalorados:

- o **grupo repetitivo** (produto, preço, unidade) vira uma linha por item, e a chave passa a ser composta: **(cnpj, data_coleta, produto)**;
- cada **multivalorado independente** vai para uma relação própria, ligada ao seu dono;
- o **endereço** é decomposto em quatro colunas. A decomposição foi validada contra a base original da ANP: 158 de 158 postos batem exatamente.

### Resultado da 1FN

| Tabela | Chave | Linhas |
|---|---|---|
| coleta_1fn | (cnpj, data_coleta, produto) | 7.717 |
| posto_servico_1fn | — (ainda com repetição) | 5.308 |
| gerente_telefone_1fn | — (ainda com repetição) | 165 |
| concorrencia_1fn | — (ainda com repetição) | 303 |

Amostra de `coleta_1fn` (mesmo posto e data do exemplo inicial):

| cnpj | data_coleta | produto | valor_venda | unidade_medida | razao_social | bandeira | municipio | gerente |
|---|---|---|---|---|---|---|---|---|
| 11222333000181 | 2026-01-07 | DIESEL | 5.90 | R$ / litro | REDE MARE COMBUSTIVEIS LTDA | BRANCA | CARIACICA | Carlos Menezes |
| 11222333000181 | 2026-01-07 | DIESEL S10 | 5.97 | R$ / litro | REDE MARE COMBUSTIVEIS LTDA | BRANCA | CARIACICA | Carlos Menezes |
| 11222333000181 | 2026-01-07 | ETANOL | 4.65 | R$ / litro | REDE MARE COMBUSTIVEIS LTDA | BRANCA | CARIACICA | Carlos Menezes |
| … | … | … | … | … | … | … | … | … |
| 11222333000181 | 2026-01-07 | GNV | 4.09 | R$ / m³ | REDE MARE COMBUSTIVEIS LTDA | BRANCA | CARIACICA | Carlos Menezes |

> **Observação crítica:** a 1FN, sozinha, **piorou** a redundância. A tabela principal saltou de 43.520 para 154.340 células, porque o cadastro inteiro do posto agora se repete a cada produto. As anomalias de atualização e exclusão continuam presentes — exatamente como alertado na Aula 04.

---

## Etapa 2 — Segunda Forma Normal (2FN)

**Regra:** estar na 1FN e todo atributo não-chave depender da chave primária **inteira**.

### Dependências parciais sobre (cnpj, data_coleta, produto)

- **DF2** — `unidade_medida` depende só de `produto`. GNV é sempre R$/m³, qualquer que seja o posto ou a data.
- **DF3** — todo o cadastro depende só de `cnpj`.
- **DF4** — `bandeira`, `semana_ref` e `observacoes` dependem de (cnpj, data_coleta), não do produto.
- Só `valor_venda` depende da chave completa (**DF1**).

### Decisão de modelagem: a bandeira muda com o tempo

Os dados reais mostram 4 postos que trocaram de bandeira no semestre — um deles três vezes (ALE → BRANCA → VIBRA). Portanto, `cnpj → bandeira` **não é** uma dependência funcional válida. Duas alternativas foram avaliadas:

| Alternativa | Vantagem | Desvantagem |
|---|---|---|
| **A. Bandeira na coleta** (cnpj, data → bandeira) | Fiel à fonte: registra a bandeira observada no dia da pesquisa | Repete a bandeira em cada coleta do posto |
| B. Tabela de vigência (posto, bandeira, data_inicio, data_fim) | Sem repetição; histórico explícito | Datas de troca exatas são desconhecidas (só sabemos entre quais coletas ocorreu) |

**Adotada: A.** A ANP não informa a data da troca, apenas a bandeira vista em cada visita. Inventar datas de vigência introduziria informação falsa. A repetição residual não gera anomalia, porque cada valor descreve um evento distinto (uma visita).

### Decomposição

| Tabela | Chave | Atributos | Linhas |
|---|---|---|---|
| posto_2fn | cnpj | cadastro + localização + grupo + gerente | 158 |
| produto_2fn | produto | unidade_medida | 6 |
| coleta_2fn | (cnpj, data_coleta) | bandeira, semana_ref, observacoes | 2.176 |
| item_coleta_2fn | (cnpj, data_coleta, produto) | valor_venda | 7.717 |
| posto_servico_2fn | (cnpj, servico) | — | 378 |
| gerente_telefone_2fn | (gerente, telefone) | — | 9 |
| concorrencia_2fn | (cnpj_proprio, cnpj_concorrente) | — | 15 |

A estrutura **coleta / item_coleta** é o mesmo padrão cabeçalho-itens de **Pedido / Item_Pedido** visto no caso GlobalTrade.

> **Anomalia herdada — o gerente de Cariacica.** Ao consolidar o cadastro, o posto 11.222.333/0001-81 apresentou dois gerentes, porque a troca de 15/04 foi registrada só em parte das linhas. O modelo não consegue "descobrir" a verdade num dado já corrompido. Adotou-se uma regra de negócio explícita: **o gerente vigente é o que apareceu por último na história do posto** (Fernanda Castro). No modelo normalizado, uma nova troca exige atualizar **1 linha** em vez de 11.

---

## Etapa 3 — Terceira Forma Normal (3FN)

**Regra:** estar na 2FN e nenhum atributo não-chave depender de outro atributo não-chave.

### Dependências transitivas removidas

| DF | Cadeia | Solução |
|---|---|---|
| DF5 | cnpj → municipio → uf → regiao | Tabelas `municipio`, `uf`, `regiao` |
| DF6 | cnpj → cnpj_raiz → grupo_economico | Tabela `grupo_economico` (chave = 8 primeiros dígitos do CNPJ) |
| DF7 | cnpj → gerente → telefones | Tabela `gerente` + `telefone_gerente` (entidade fraca) |
| DF8 | (cnpj, data) → data_coleta → semana_ref | Coluna **eliminada**: é derivável e será calculada na VIEW |

Além disso, os domínios textuais (`produto`, `bandeira`, `servico`) ganharam tabelas próprias com chave substituta. Não é exigência da 3FN, e sim de **integridade de domínio**: com FOREIGN KEY, o banco recusa uma bandeira "IPIRANGAA" digitada errado.

### Esquema final (3FN)

| Tabela | PK | FKs / UK | Linhas |
|---|---|---|---|
| regiao | sigla_regiao | — | 1 |
| uf | sigla_uf | sigla_regiao → regiao | 1 |
| municipio | id_municipio | sigla_uf → uf · UK(nome, sigla_uf) | 10 |
| grupo_economico | cnpj_raiz | — | 146 |
| gerente | id_gerente | — | 6 |
| telefone_gerente | (id_gerente, telefone) | id_gerente → gerente | 9 |
| posto | cnpj | cnpj_raiz → grupo_economico · id_municipio → municipio · id_gerente → gerente (opcional) | 158 |
| servico | id_servico | UK(nome) | 6 |
| posto_servico | (cnpj, id_servico) | → posto · → servico | 378 |
| concorrencia | (cnpj_proprio, cnpj_concorrente) | ambos → posto | 15 |
| produto | id_produto | UK(nome) | 6 |
| bandeira | id_bandeira | UK(nome) | 6 |
| coleta | id_coleta | cnpj → posto · id_bandeira → bandeira · UK(cnpj, data_coleta) | 2.176 |
| item_coleta | (id_coleta, id_produto) | → coleta · → produto | 7.717 |

Destaques estruturais para o DER:

- **Entidades fracas:** `telefone_gerente` (não existe sem gerente) e `item_coleta` (não existe sem coleta).
- **N:M:** posto × serviço, e o **auto-relacionamento** posto × posto em `concorrencia`. Os dois postos Maré de Cariacica compartilham os mesmos 3 concorrentes, o que prova a necessidade do N:M.
- **Regiao/UF com 1 linha:** reflete o recorte (ES). O modelo já suporta a base nacional sem alteração.

---

## Resultado: anomalias resolvidas e ganhos mensuráveis

| Anomalia | Na planilha | No modelo 3FN |
|---|---|---|
| Inserção | Posto novo ou concorrente só entra quando houver coleta | `INSERT` em `posto`, sem coleta |
| Atualização | Trocar gerente = editar 11 linhas (3 ficaram erradas) | `UPDATE` em 1 linha de `posto` |
| Exclusão | Apagar coletas antigas apaga o cadastro do concorrente | Excluir de `coleta` preserva `posto` e `concorrencia` |

| Indicador | Antes | Depois (3FN) |
|---|---|---|
| Células totais | 43.720 | 36.953 (−15,5%) |
| Células cadastrais repetidas | 16.224 | 0 |
| Grafias divergentes de razão social | 79 postos | Impossível (1 linha por CNPJ) |
| Associações posto-serviço | 5.308 (repetidas) | 378 |
| Unidade de medida registrada | 7.717 vezes | 6 vezes |
