-- =============================================================================
-- 05_roi.sql — Estimativa de impacto financeiro (ROI) a partir das VIEWs
-- Execucao: psql -d rede_mare -f sql/05_roi.sql
--
-- PREMISSAS (declaradas no relatorio; altere aqui para simular cenarios):
--   * Volume medio por posto: 178.000 litros/mes (Fecombustiveis, apresentacao
--     na Camara dos Deputados, 2017).
--   * Mix de vendas de um posto urbano (hipotese do autor).
--   * Captura: fracao do gap que a rede consegue recuperar reajustando o preco
--     sem perder volume. Cenarios: 25% (conservador), 50% (base), 100% (teto).
--   * GNV fica fora do calculo (unidade em m3 e venda pouco representativa).
-- =============================================================================

-- Garante leitura correta de acentos e do simbolo m3 no Windows
SET client_encoding = 'UTF8';

SET search_path TO rede_mare;

WITH premissa_mix (produto, participacao) AS (
    VALUES ('GASOLINA',           0.50),
           ('GASOLINA ADITIVADA', 0.10),
           ('ETANOL',             0.15),
           ('DIESEL S10',         0.20),
           ('DIESEL',             0.05)
),
premissa_volume AS (
    SELECT 178000::NUMERIC AS litros_mes_posto
),
-- Margem deixada na mesa: so conta as semanas em que o posto esteve ABAIXO
-- da media dos concorrentes diretos (gap negativo).
oportunidade AS (
    SELECT
        pn.posto,
        pn.produto,
        pn.pct_semanas_abaixo / 100.0            AS freq_abaixo,
        ABS(pn.gap_medio_quando_abaixo_rs)       AS gap_rs_litro,
        v.litros_mes_posto * m.participacao      AS litros_mes_produto
    FROM vw_painel_rede_mare pn
    JOIN premissa_mix m ON m.produto = pn.produto
    CROSS JOIN premissa_volume v
    WHERE pn.gap_medio_quando_abaixo_rs IS NOT NULL
)
SELECT
    posto,
    produto,
    ROUND(freq_abaixo * 100, 1)                              AS pct_semanas_abaixo,
    gap_rs_litro,
    ROUND(litros_mes_produto)                                AS litros_mes,
    ROUND(litros_mes_produto * freq_abaixo * gap_rs_litro, 2) AS margem_na_mesa_mes_rs
FROM oportunidade
ORDER BY margem_na_mesa_mes_rs DESC;


-- Consolidado da rede por cenario de captura (mensal e anual)
WITH premissa_mix (produto, participacao) AS (
    VALUES ('GASOLINA', 0.50), ('GASOLINA ADITIVADA', 0.10),
           ('ETANOL', 0.15), ('DIESEL S10', 0.20), ('DIESEL', 0.05)
),
total AS (
    SELECT SUM(178000 * m.participacao
               * (pn.pct_semanas_abaixo / 100.0)
               * ABS(pn.gap_medio_quando_abaixo_rs)) AS margem_mes
    FROM vw_painel_rede_mare pn
    JOIN premissa_mix m ON m.produto = pn.produto
    WHERE pn.gap_medio_quando_abaixo_rs IS NOT NULL
),
cenario (nome, captura) AS (
    VALUES ('Conservador', 0.25), ('Base', 0.50), ('Teto', 1.00)
)
SELECT
    c.nome                                   AS cenario,
    (c.captura * 100)::INT || '%'            AS captura,
    ROUND(t.margem_mes * c.captura, 2)       AS ganho_mensal_rs,
    ROUND(t.margem_mes * c.captura * 12, 2)  AS ganho_anual_rs
FROM total t
CROSS JOIN cenario c
ORDER BY c.captura;
