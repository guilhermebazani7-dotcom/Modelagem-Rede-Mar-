-- =============================================================================
-- 02_carga.sql — Carga das tabelas 3FN geradas por dados/03_normalizar.py
-- Execucao (a partir da raiz do repositorio, pois \copy usa caminho relativo):
--     psql -d rede_mare -f sql/02_carga.sql
-- A ordem respeita as dependencias: pais antes de filhos.
-- Tudo roda numa unica transacao: se qualquer constraint falhar, nada e gravado.
-- =============================================================================

-- Garante leitura correta de acentos e do simbolo m3 no Windows
SET client_encoding = 'UTF8';

\set ON_ERROR_STOP on
SET search_path TO rede_mare;

BEGIN;

\copy regiao           FROM 'dados/normalizado/3fn/regiao.csv'           WITH (FORMAT csv, HEADER, DELIMITER ';', ENCODING 'UTF8')
\copy uf               FROM 'dados/normalizado/3fn/uf.csv'               WITH (FORMAT csv, HEADER, DELIMITER ';', ENCODING 'UTF8')
\copy municipio        FROM 'dados/normalizado/3fn/municipio.csv'        WITH (FORMAT csv, HEADER, DELIMITER ';', ENCODING 'UTF8')
\copy grupo_economico  FROM 'dados/normalizado/3fn/grupo_economico.csv'  WITH (FORMAT csv, HEADER, DELIMITER ';', ENCODING 'UTF8')
\copy gerente          FROM 'dados/normalizado/3fn/gerente.csv'          WITH (FORMAT csv, HEADER, DELIMITER ';', ENCODING 'UTF8')
\copy telefone_gerente FROM 'dados/normalizado/3fn/telefone_gerente.csv' WITH (FORMAT csv, HEADER, DELIMITER ';', ENCODING 'UTF8')
\copy posto            FROM 'dados/normalizado/3fn/posto.csv'            WITH (FORMAT csv, HEADER, DELIMITER ';', ENCODING 'UTF8')
\copy servico          FROM 'dados/normalizado/3fn/servico.csv'          WITH (FORMAT csv, HEADER, DELIMITER ';', ENCODING 'UTF8')
\copy posto_servico    FROM 'dados/normalizado/3fn/posto_servico.csv'    WITH (FORMAT csv, HEADER, DELIMITER ';', ENCODING 'UTF8')
\copy concorrencia (cnpj_proprio, cnpj_concorrente) FROM 'dados/normalizado/3fn/concorrencia.csv' WITH (FORMAT csv, HEADER, DELIMITER ';', ENCODING 'UTF8')
\copy produto          FROM 'dados/normalizado/3fn/produto.csv'          WITH (FORMAT csv, HEADER, DELIMITER ';', ENCODING 'UTF8')
\copy bandeira         FROM 'dados/normalizado/3fn/bandeira.csv'         WITH (FORMAT csv, HEADER, DELIMITER ';', ENCODING 'UTF8')
\copy coleta           FROM 'dados/normalizado/3fn/coleta.csv'           WITH (FORMAT csv, HEADER, DELIMITER ';', ENCODING 'UTF8')
\copy item_coleta      FROM 'dados/normalizado/3fn/item_coleta.csv'      WITH (FORMAT csv, HEADER, DELIMITER ';', ENCODING 'UTF8')

-- As chaves substitutas vieram prontas do CSV; o contador IDENTITY precisa
-- avancar para que o proximo INSERT nao colida com um id ja existente.
SELECT setval(pg_get_serial_sequence('municipio', 'id_municipio'), MAX(id_municipio)) FROM municipio;
SELECT setval(pg_get_serial_sequence('gerente',   'id_gerente'),   MAX(id_gerente))   FROM gerente;
SELECT setval(pg_get_serial_sequence('servico',   'id_servico'),   MAX(id_servico))   FROM servico;
SELECT setval(pg_get_serial_sequence('produto',   'id_produto'),   MAX(id_produto))   FROM produto;
SELECT setval(pg_get_serial_sequence('bandeira',  'id_bandeira'),  MAX(id_bandeira))  FROM bandeira;
SELECT setval(pg_get_serial_sequence('coleta',    'id_coleta'),    MAX(id_coleta))    FROM coleta;

COMMIT;

-- Conferencia rapida: linhas carregadas por tabela
SELECT 'regiao' AS tabela, COUNT(*) AS linhas FROM regiao
UNION ALL SELECT 'uf', COUNT(*) FROM uf
UNION ALL SELECT 'municipio', COUNT(*) FROM municipio
UNION ALL SELECT 'grupo_economico', COUNT(*) FROM grupo_economico
UNION ALL SELECT 'gerente', COUNT(*) FROM gerente
UNION ALL SELECT 'telefone_gerente', COUNT(*) FROM telefone_gerente
UNION ALL SELECT 'posto', COUNT(*) FROM posto
UNION ALL SELECT 'servico', COUNT(*) FROM servico
UNION ALL SELECT 'posto_servico', COUNT(*) FROM posto_servico
UNION ALL SELECT 'concorrencia', COUNT(*) FROM concorrencia
UNION ALL SELECT 'produto', COUNT(*) FROM produto
UNION ALL SELECT 'bandeira', COUNT(*) FROM bandeira
UNION ALL SELECT 'coleta', COUNT(*) FROM coleta
UNION ALL SELECT 'item_coleta', COUNT(*) FROM item_coleta;
