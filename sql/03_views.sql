-- =============================================================================
-- 03_views.sql — VIEWs analiticas para a diretoria da Rede Mare
-- Execucao: psql -d rede_mare -f sql/03_views.sql
--
-- A normalizacao protege a OPERACAO (sem anomalias). As VIEWs reconstroem a
-- visao ANALITICA com seguranca: os JOINs sao feitos pelo banco, sempre a
-- partir de uma unica fonte da verdade, em vez de copiados a mao na planilha.
-- Todos os JOINs usam a sintaxe ANSI (JOIN ... ON), separando a logica de
-- conexao da logica de filtro (Aula 05).
-- =============================================================================

-- Garante leitura correta de acentos e do simbolo m3 no Windows
SET client_encoding = 'UTF8';

SET search_path TO rede_mare;


-- -----------------------------------------------------------------------------
-- VIEW 1 — Visao desnormalizada para dashboard (Power BI / Looker / Excel)
-- Grao: 1 linha = 1 preco de 1 produto em 1 coleta.
-- Substitui a "planilha monstro", agora gerada sem redundancia armazenada.
-- A semana, que era digitada a mao (semana_ref), passa a ser calculada.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_coleta_completa AS
SELECT
    c.id_coleta,
    c.data_coleta,
    DATE_TRUNC('week', c.data_coleta)::DATE          AS semana_inicio,
    TO_CHAR(c.data_coleta, 'YYYY-MM')                AS mes,
    p.cnpj,
    CASE WHEN p.tipo_posto = 'PROPRIO'
         THEN 'MARE ' || p.bairro
         ELSE p.razao_social
    END                                              AS nome_exibicao,
    p.tipo_posto,
    g.nome                                           AS grupo_economico,
    b.nome                                           AS bandeira,
    p.bairro,
    m.nome                                           AS municipio,
    u.sigla_uf                                       AS uf,
    r.nome                                           AS regiao,
    pr.nome                                          AS produto,
    pr.unidade_medida,
    ic.valor_venda
FROM coleta c
JOIN item_coleta     ic ON ic.id_coleta    = c.id_coleta
JOIN produto         pr ON pr.id_produto   = ic.id_produto
JOIN bandeira        b  ON b.id_bandeira   = c.id_bandeira
JOIN posto           p  ON p.cnpj          = c.cnpj
JOIN grupo_economico g  ON g.cnpj_raiz     = p.cnpj_raiz
JOIN municipio       m  ON m.id_municipio  = p.id_municipio
JOIN uf              u  ON u.sigla_uf      = m.sigla_uf
JOIN regiao          r  ON r.sigla_regiao  = u.sigla_regiao;

COMMENT ON VIEW vw_coleta_completa IS
    'Visao desnormalizada (1 linha por preco coletado) para ferramentas de BI.';


-- -----------------------------------------------------------------------------
-- VIEW 2 — Posicionamento de preco vs. concorrentes diretos (semanal)
-- Pergunta da diretoria: "Em cada posto e produto, estamos acima ou abaixo
-- dos concorrentes que monitoramos?"
-- A ANP visita os postos em dias diferentes da semana; por isso a comparacao
-- e feita por semana (grao semanal), e nao por data exata.
-- Faixa de tolerancia: +/- 1% e considerado ALINHADO.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_posicionamento_concorrencia AS
WITH preco_semanal AS (
    SELECT
        c.cnpj,
        DATE_TRUNC('week', c.data_coleta)::DATE AS semana_inicio,
        ic.id_produto,
        AVG(ic.valor_venda)                     AS preco
    FROM coleta c
    JOIN item_coleta ic ON ic.id_coleta = c.id_coleta
    GROUP BY c.cnpj, DATE_TRUNC('week', c.data_coleta), ic.id_produto
),
comparacao AS (
    SELECT
        prop.semana_inicio,
        cc.cnpj_proprio,
        prop.id_produto,
        prop.preco                     AS preco_proprio,
        AVG(conc.preco)                AS preco_medio_concorrentes,
        MIN(conc.preco)                AS menor_preco_concorrente,
        COUNT(conc.cnpj)               AS concorrentes_pesquisados
    FROM concorrencia cc
    JOIN preco_semanal prop
      ON prop.cnpj = cc.cnpj_proprio
    JOIN preco_semanal conc
      ON  conc.cnpj          = cc.cnpj_concorrente
      AND conc.semana_inicio = prop.semana_inicio
      AND conc.id_produto    = prop.id_produto
    GROUP BY prop.semana_inicio, cc.cnpj_proprio, prop.id_produto, prop.preco
)
SELECT
    cp.semana_inicio,
    cp.cnpj_proprio,
    'MARE ' || p.bairro                                     AS posto,
    m.nome                                                  AS municipio,
    pr.nome                                                 AS produto,
    ROUND(cp.preco_proprio, 3)                              AS preco_proprio,
    ROUND(cp.preco_medio_concorrentes, 3)                   AS preco_medio_concorrentes,
    ROUND(cp.menor_preco_concorrente, 3)                    AS menor_preco_concorrente,
    cp.concorrentes_pesquisados,
    ROUND(cp.preco_proprio - cp.preco_medio_concorrentes, 3) AS diferenca_rs,
    ROUND(100 * (cp.preco_proprio / cp.preco_medio_concorrentes - 1), 2)
                                                            AS diferenca_pct,
    CASE
        WHEN cp.preco_proprio > cp.preco_medio_concorrentes * 1.01 THEN 'ACIMA'
        WHEN cp.preco_proprio < cp.preco_medio_concorrentes * 0.99 THEN 'ABAIXO'
        ELSE 'ALINHADO'
    END                                                     AS posicao
FROM comparacao cp
JOIN posto     p  ON p.cnpj         = cp.cnpj_proprio
JOIN municipio m  ON m.id_municipio = p.id_municipio
JOIN produto   pr ON pr.id_produto  = cp.id_produto;

COMMENT ON VIEW vw_posicionamento_concorrencia IS
    'Preco semanal de cada posto proprio vs. media dos concorrentes diretos.';


-- -----------------------------------------------------------------------------
-- VIEW 3 — Painel executivo por posto proprio (consolidado do semestre)
-- Pergunta da diretoria: "Onde estamos deixando margem na mesa (abaixo do
-- mercado) e onde arriscamos perder volume (acima do mercado)?"
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_painel_rede_mare AS
SELECT
    posto,
    municipio,
    produto,
    COUNT(*)                                              AS semanas_comparadas,
    ROUND(100.0 * COUNT(*) FILTER (WHERE posicao = 'ABAIXO') / COUNT(*), 1)
                                                          AS pct_semanas_abaixo,
    ROUND(100.0 * COUNT(*) FILTER (WHERE posicao = 'ACIMA') / COUNT(*), 1)
                                                          AS pct_semanas_acima,
    ROUND(AVG(diferenca_rs), 3)                           AS gap_medio_rs,
    ROUND(AVG(diferenca_rs) FILTER (WHERE posicao = 'ABAIXO'), 3)
                                                          AS gap_medio_quando_abaixo_rs
FROM vw_posicionamento_concorrencia
GROUP BY posto, municipio, produto;

COMMENT ON VIEW vw_painel_rede_mare IS
    'Resumo semestral: frequencia e tamanho do gap de preco por posto/produto.';


-- -----------------------------------------------------------------------------
-- VIEW 4 — Evolucao mensal do preco por bandeira
-- Pergunta da diretoria: "Qual o desconto historico da bandeira branca frente
-- as bandeiras? Ele esta aumentando ou diminuindo?"
-- Usa a bandeira OBSERVADA no dia (decisao de modelagem da 2FN): um posto que
-- trocou de bandeira contribui para cada uma no periodo correto.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_evolucao_preco_bandeira AS
SELECT
    mes,
    produto,
    bandeira,
    COUNT(*)                                  AS precos_coletados,
    ROUND(AVG(valor_venda), 3)                AS preco_medio,
    ROUND(MIN(valor_venda), 3)                AS preco_minimo,
    ROUND(MAX(valor_venda), 3)                AS preco_maximo,
    -- Media de mercado ponderada pelo numero de precos coletados no mes
    ROUND(AVG(valor_venda)
          - SUM(SUM(valor_venda)) OVER (PARTITION BY mes, produto)
            / SUM(COUNT(*)) OVER (PARTITION BY mes, produto), 3)
                                              AS dif_vs_media_mercado_rs
FROM vw_coleta_completa
GROUP BY mes, produto, bandeira;

COMMENT ON VIEW vw_evolucao_preco_bandeira IS
    'Preco medio mensal por bandeira e produto, com diferenca vs. media.';
