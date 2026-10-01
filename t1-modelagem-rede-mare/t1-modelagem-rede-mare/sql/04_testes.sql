-- =============================================================================
-- 04_testes.sql — Prova de que as anomalias sumiram e as constraints funcionam
-- Execucao: psql -d rede_mare -f sql/04_testes.sql
--
-- Tudo roda dentro de uma transacao encerrada com ROLLBACK: os testes alteram
-- dados para provar comportamentos, mas o banco volta ao estado original.
-- Saida: uma tabela com cada teste, o resultado esperado e o status.
-- =============================================================================

-- Garante leitura correta de acentos e do simbolo m3 no Windows
SET client_encoding = 'UTF8';

\set ON_ERROR_STOP on
SET search_path TO rede_mare;
BEGIN;

CREATE TEMP TABLE resultado_teste (
    ordem     SERIAL,
    grupo     TEXT,
    teste     TEXT,
    esperado  TEXT,
    obtido    TEXT,
    status    TEXT,
    detalhe   TEXT
) ON COMMIT DROP;

-- Registra o resultado de um teste que DEVE ser aceito pelo banco.
CREATE FUNCTION pg_temp.registrar(p_grupo TEXT, p_teste TEXT,
                                  p_esperado TEXT, p_obtido TEXT,
                                  p_detalhe TEXT DEFAULT NULL)
RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO resultado_teste (grupo, teste, esperado, obtido, status,
                                 detalhe)
    VALUES (p_grupo, p_teste, p_esperado, p_obtido,
            CASE WHEN p_esperado = p_obtido THEN 'PASSOU' ELSE 'FALHOU' END,
            p_detalhe);
END $$;

-- Executa um comando que DEVE ser rejeitado com um SQLSTATE especifico.
-- 23514 = check_violation | 23503 = foreign_key_violation
-- 23505 = unique_violation
CREATE FUNCTION pg_temp.esperar_erro(p_grupo TEXT, p_teste TEXT,
                                     p_comando TEXT, p_sqlstate TEXT)
RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    EXECUTE p_comando;
    PERFORM pg_temp.registrar(p_grupo, p_teste, 'rejeitado ' || p_sqlstate,
                              'ACEITO (nao deveria)');
EXCEPTION WHEN OTHERS THEN
    PERFORM pg_temp.registrar(p_grupo, p_teste, 'rejeitado ' || p_sqlstate,
                              'rejeitado ' || SQLSTATE);
END $$;


-- =============================================================================
-- GRUPO A — As tres anomalias da planilha deixaram de existir
-- =============================================================================

-- A1. INSERCAO: cadastrar o 6o posto da rede ANTES de qualquer coleta de preco.
-- Na planilha isso era impossivel (nao existia linha sem data/preco).
DO $$
DECLARE v_coletas INT;
BEGIN
    INSERT INTO posto (cnpj, razao_social, tipo_posto, cnpj_raiz, logradouro,
                       numero, bairro, cep, id_municipio)
    VALUES ('11222333000696', 'REDE MARE COMBUSTIVEIS LTDA', 'PROPRIO',
            '11222333', 'AVENIDA DANTE MICHELINI', '1500', 'JARDIM CAMBURI',
            '29060-235',
            (SELECT id_municipio FROM municipio WHERE nome = 'VITORIA'));

    SELECT COUNT(*) INTO v_coletas FROM coleta WHERE cnpj = '11222333000696';
    PERFORM pg_temp.registrar('A. Anomalias', 'A1 Inserir posto sem coleta',
        'posto cadastrado com 0 coletas',
        'posto cadastrado com ' || v_coletas || ' coletas');
END $$;

-- A2. ATUALIZACAO: trocar o gerente do posto de Cariacica.
-- Na planilha: 11 linhas a editar (3 ficaram erradas). Aqui: 1 linha.
DO $$
DECLARE
    v_linhas     INT;
    v_novo       INT;
    v_distintos  INT;
BEGIN
    INSERT INTO gerente (nome) VALUES ('Roberto Sampaio')
    RETURNING id_gerente INTO v_novo;

    UPDATE posto SET id_gerente = v_novo WHERE cnpj = '11222333000181';
    GET DIAGNOSTICS v_linhas = ROW_COUNT;

    -- Todas as coletas do posto passam a enxergar o mesmo (novo) gerente
    SELECT COUNT(DISTINCT g.nome) INTO v_distintos
    FROM coleta c
    JOIN posto p   ON p.cnpj = c.cnpj
    JOIN gerente g ON g.id_gerente = p.id_gerente
    WHERE c.cnpj = '11222333000181';

    PERFORM pg_temp.registrar('A. Anomalias', 'A2 Trocar gerente',
        '1 linha alterada, 1 gerente visivel',
        v_linhas || ' linha alterada, ' || v_distintos || ' gerente visivel',
        'na planilha: 11 linhas a editar, 3 ficaram desatualizadas');
END $$;

-- A3. ATUALIZACAO: corrigir a razao social de um concorrente.
-- A mudanca em 1 linha se propaga para todas as linhas da VIEW de dashboard.
DO $$
DECLARE
    v_linhas     INT;
    v_linhas_vw  INT;
    v_nomes      INT;
BEGIN
    UPDATE posto SET razao_social = 'MAIS COMBUSTIVEIS CARIACICA LTDA'
    WHERE cnpj = '15226314000184';
    GET DIAGNOSTICS v_linhas = ROW_COUNT;

    SELECT COUNT(*), COUNT(DISTINCT nome_exibicao) INTO v_linhas_vw, v_nomes
    FROM vw_coleta_completa WHERE cnpj = '15226314000184';

    PERFORM pg_temp.registrar('A. Anomalias', 'A3 Renomear concorrente',
        '1 linha alterada, 1 nome na view',
        v_linhas || ' linha alterada, ' || v_nomes || ' nome na view',
        v_linhas_vw || ' linhas da view refletem a correcao');
END $$;

-- A4. EXCLUSAO: apagar todo o historico de coletas de um concorrente.
-- Na planilha isso apagava o cadastro e o vinculo de concorrencia.
-- Aqui: itens caem em CASCADE, mas posto e concorrencia permanecem.
DO $$
DECLARE
    v_coletas  INT;
    v_itens    INT;
    v_posto    INT;
    v_vinculos INT;
BEGIN
    DELETE FROM coleta WHERE cnpj = '13814642000176';
    GET DIAGNOSTICS v_coletas = ROW_COUNT;

    SELECT COUNT(*) INTO v_itens
    FROM item_coleta ic
    WHERE NOT EXISTS (SELECT 1 FROM coleta c WHERE c.id_coleta = ic.id_coleta);
    SELECT COUNT(*) INTO v_posto FROM posto WHERE cnpj = '13814642000176';
    SELECT COUNT(*) INTO v_vinculos
    FROM concorrencia WHERE cnpj_concorrente = '13814642000176';

    PERFORM pg_temp.registrar('A. Anomalias', 'A4 Apagar coletas de concorrente',
        'posto=1, vinculos=2, itens orfaos=0',
        'posto=' || v_posto || ', vinculos=' || v_vinculos
        || ', itens orfaos=' || v_itens,
        v_coletas || ' coletas apagadas; itens removidos em CASCADE');
END $$;

-- A5. EXCLUSAO protegida: apagar um posto que tem historico de precos.
DO $t$ BEGIN PERFORM pg_temp.esperar_erro('A. Anomalias',
    'A5 Apagar posto com historico (RESTRICT)',
    $$DELETE FROM posto WHERE cnpj = '00580488000173'$$, '23503'); END $t$;


-- =============================================================================
-- GRUPO B — Integridade de dominio (CHECK)
-- =============================================================================
DO $t$ BEGIN PERFORM pg_temp.esperar_erro('B. CHECK', 'B1 Preco negativo',
    $$INSERT INTO item_coleta VALUES (1, 6, -4.99)$$, '23514'); END $t$;

DO $t$ BEGIN PERFORM pg_temp.esperar_erro('B. CHECK', 'B2 CNPJ com letras',
    $$UPDATE posto SET cnpj = '11222333ABCD81' WHERE cnpj = '11222333000181'$$,
    '23514'); END $t$;

DO $t$ BEGIN PERFORM pg_temp.esperar_erro('B. CHECK', 'B3 Gerente em posto concorrente',
    $$UPDATE posto SET id_gerente = 1 WHERE cnpj = '00580488000173'$$, '23514'); END $t$;

DO $t$ BEGIN PERFORM pg_temp.esperar_erro('B. CHECK', 'B4 Raiz incoerente com o CNPJ',
    $$UPDATE posto SET cnpj_raiz = '00580488' WHERE cnpj = '11222333000181'$$,
    '23514'); END $t$;

DO $t$ BEGIN PERFORM pg_temp.esperar_erro('B. CHECK', 'B5 Unidade de medida invalida',
    $$INSERT INTO produto (nome, unidade_medida) VALUES ('GLP', 'R$/kg')$$,
    '23514'); END $t$;

DO $t$ BEGIN PERFORM pg_temp.esperar_erro('B. CHECK', 'B6 Telefone fora do padrao',
    $$INSERT INTO telefone_gerente VALUES (1, '27 99999999')$$, '23514'); END $t$;

DO $t$ BEGIN PERFORM pg_temp.esperar_erro('B. CHECK', 'B7 Coleta com data futura',
    $$INSERT INTO coleta (cnpj, data_coleta, id_bandeira)
      VALUES ('00580488000173', CURRENT_DATE + 30, 1)$$, '23514'); END $t$;

DO $t$ BEGIN PERFORM pg_temp.esperar_erro('B. CHECK', 'B8 Posto concorrente de si mesmo',
    $$INSERT INTO concorrencia (cnpj_proprio, cnpj_concorrente)
      VALUES ('11222333000181', '11222333000181')$$, '23514'); END $t$;


-- =============================================================================
-- GRUPO C — Integridade de entidade e referencial (PK, UNIQUE, FK)
-- =============================================================================
DO $t$ BEGIN PERFORM pg_temp.esperar_erro('C. PK/UK/FK', 'C1 Mesma coleta duas vezes (UK)',
    $$INSERT INTO coleta (cnpj, data_coleta, id_bandeira)
      SELECT cnpj, data_coleta, id_bandeira FROM coleta LIMIT 1$$, '23505'); END $t$;

DO $t$ BEGIN PERFORM pg_temp.esperar_erro('C. PK/UK/FK', 'C2 Mesmo produto 2x na coleta (PK)',
    $$INSERT INTO item_coleta
      SELECT id_coleta, id_produto, 5.00 FROM item_coleta LIMIT 1$$, '23505'); END $t$;

DO $t$ BEGIN PERFORM pg_temp.esperar_erro('C. PK/UK/FK', 'C3 Bandeira duplicada (UK)',
    $$INSERT INTO bandeira (nome) VALUES ('IPIRANGA')$$, '23505'); END $t$;

DO $t$ BEGIN PERFORM pg_temp.esperar_erro('C. PK/UK/FK', 'C4 Preco de produto inexistente',
    $$INSERT INTO item_coleta VALUES (1, 999, 5.00)$$, '23503'); END $t$;

DO $t$ BEGIN PERFORM pg_temp.esperar_erro('C. PK/UK/FK', 'C5 Coleta de bandeira inexistente',
    $$INSERT INTO coleta (cnpj, data_coleta, id_bandeira)
      VALUES ('00580488000173', DATE '2026-07-01', 999)$$, '23503'); END $t$;

DO $t$ BEGIN PERFORM pg_temp.esperar_erro('C. PK/UK/FK',
    'C6 Concorrente cadastrado como proprio',
    $$INSERT INTO concorrencia (cnpj_proprio, cnpj_concorrente)
      VALUES ('00580488000173', '11222333000181')$$, '23503'); END $t$;


-- =============================================================================
-- Relatorio final
-- =============================================================================
SELECT grupo, teste, esperado, obtido, status, detalhe
FROM resultado_teste ORDER BY ordem;

SELECT COUNT(*) FILTER (WHERE status = 'PASSOU') AS passou,
       COUNT(*) FILTER (WHERE status = 'FALHOU') AS falhou,
       COUNT(*)                                  AS total
FROM resultado_teste;

ROLLBACK;
