"""
03_normalizar.py
----------------
Executa, passo a passo, a normalizacao da planilha_caotica.csv:

    Etapa 0 - Limpeza de formato (nao e normalizacao, mas e pre-requisito)
    Etapa 1 - 1FN: atributos atomicos, sem grupos repetitivos
    Etapa 2 - 2FN: remocao de dependencias parciais
    Etapa 3 - 3FN: remocao de dependencias transitivas

Cada etapa grava suas tabelas em normalizado/<etapa>/ para que o processo
possa ser auditado. As tabelas de normalizado/3fn/ sao a carga do SQL.

Uso:
    python 03_normalizar.py planilha_caotica.csv [anp_recorte_ES.csv]
O segundo argumento (opcional) valida a decomposicao do endereco contra a
base original da ANP.
"""
import os
import re
import sys
import unicodedata

import pandas as pd

REGIOES = {"N": "Norte", "NE": "Nordeste", "CO": "Centro-Oeste",
           "SE": "Sudeste", "S": "Sul"}
MUNICIPIOS_CANONICOS = {"V. VELHA": "VILA VELHA"}
UNIDADES_CANONICAS = {"R$/l": "R$ / litro"}
SEP_LISTA = r"\s*;\s*|\s+/\s+|\s*,\s*"
RE_ENDERECO = re.compile(
    r"^(?P<logradouro>.*), (?P<numero>[^,]*?)(?: - (?P<complemento>.*))?$")


# ---------------------------------------------------------------- utilidades
def sem_acento(texto: str) -> str:
    """Remove acentos: 'VITÓRIA' -> 'VITORIA'."""
    return (unicodedata.normalize("NFKD", texto)
            .encode("ascii", "ignore").decode())


def dividir(valor, padrao: str = SEP_LISTA) -> list:
    """Divide uma celula multivalorada em itens atomicos."""
    if pd.isna(valor) or not str(valor).strip():
        return []
    return [item.strip() for item in re.split(padrao, str(valor))
            if item.strip()]


def decompor_endereco(endereco: str) -> dict:
    """'RUA X, 10 - FUNDOS - CENTRO' -> logradouro, numero, complemento,
    bairro. O bairro e sempre o ultimo trecho apos ' - '."""
    esquerda, _, bairro = endereco.rpartition(" - ")
    partes = RE_ENDERECO.match(esquerda).groupdict()
    partes["bairro"] = bairro
    return partes


def salvar(tabelas: dict, etapa: str) -> None:
    """Grava cada DataFrame em normalizado/<etapa>/<nome>.csv."""
    pasta = os.path.join("normalizado", etapa)
    os.makedirs(pasta, exist_ok=True)
    print(f"\n[{etapa.upper()}]")
    for nome, tabela in tabelas.items():
        tabela.to_csv(os.path.join(pasta, f"{nome}.csv"), sep=";",
                      index=False, encoding="utf-8")
        print(f"  {nome:<22} {len(tabela):>6} linhas x "
              f"{tabela.shape[1]:>2} colunas = {tabela.size:>7} celulas")


# ------------------------------------------------------- etapa 0: limpeza
def limpar(df: pd.DataFrame) -> pd.DataFrame:
    """Padroniza formatos. Nao altera a estrutura (ainda e tabela universal).
    """
    df = df.drop_duplicates().copy()
    df["cnpj"] = df["cnpj"].str.replace(r"\D", "", regex=True).str.zfill(14)
    # Formatos explicitos: 'format="mixed"' com dayfirst=True inverte dia e
    # mes em datas ISO (2026-02-11 viraria 2026-11-02) sem gerar erro.
    br = pd.to_datetime(df["data_coleta"], format="%d/%m/%Y", errors="coerce")
    iso = pd.to_datetime(df["data_coleta"], format="%Y-%m-%d",
                         errors="coerce")
    datas = br.fillna(iso)
    if datas.isna().any():
        invalidas = df.loc[datas.isna(), "data_coleta"].unique()
        raise ValueError(f"Datas em formato desconhecido: {invalidas}")
    df["data_coleta"] = datas.dt.date

    municipio = df["municipio"].str.strip().str.upper().map(sem_acento)
    df["municipio"] = municipio.replace(MUNICIPIOS_CANONICOS)

    # Razao social canonica = grafia mais frequente por CNPJ
    nome = df["razao_social"].str.upper().str.rstrip(".").str.strip()
    df["razao_social"] = nome.groupby(df["cnpj"]).transform(
        lambda s: s.mode().iloc[0])

    for errado, certo in UNIDADES_CANONICAS.items():
        df["unidades"] = df["unidades"].str.replace(errado, certo,
                                                    regex=False)
    df["servicos"] = df["servicos"].str.title()
    return df


# ----------------------------------------------------------- etapa 1: 1FN
def aplicar_1fn(df: pd.DataFrame) -> dict:
    """Grupo repetitivo (produto, preco, unidade) vira uma linha por item.
    Atributos multivalorados independentes vao para relacoes proprias,
    evitando a explosao cartesiana de achata-los juntos.
    O endereco composto e decomposto em atributos atomicos."""
    linhas = []
    for _, r in df.iterrows():
        produtos = dividir(r["produtos"], r"\s*,\s*")
        precos = dividir(r["precos"], r"\s+/\s+")
        unidades = dividir(r["unidades"], r"\s*;\s*")
        for produto, preco, unidade in zip(produtos, precos, unidades):
            linhas.append({**r.to_dict(), "produto": produto,
                           "valor_venda": float(preco.replace(",", ".")),
                           "unidade_medida": unidade})
    base = pd.DataFrame(linhas)

    endereco = pd.DataFrame(base["endereco"].map(decompor_endereco).tolist())
    base = pd.concat([base.reset_index(drop=True), endereco], axis=1)

    colunas = ["cnpj", "data_coleta", "produto", "valor_venda",
               "unidade_medida", "semana_ref", "tipo_posto", "razao_social",
               "grupo_economico", "bandeira", "logradouro", "numero",
               "complemento", "bairro", "cep", "municipio", "uf", "regiao",
               "gerente", "observacoes"]
    coleta_1fn = base[colunas]

    def explodir(coluna: str, novo_nome: str) -> pd.DataFrame:
        pares = df[["cnpj", coluna]].copy()
        pares[novo_nome] = pares[coluna].map(dividir)
        pares = pares.explode(novo_nome).dropna(subset=[novo_nome])
        return pares[["cnpj", novo_nome]]

    posto_servico = explodir("servicos", "servico")
    telefones = df[["gerente", "telefones_gerente"]].dropna().copy()
    telefones["telefone"] = telefones["telefones_gerente"].map(
        lambda v: dividir(v, r"\s+/\s+"))
    telefones = telefones.explode("telefone")[["gerente", "telefone"]]
    concorrencia = explodir("concorrentes_diretos", "cnpj_concorrente")
    concorrencia["cnpj_concorrente"] = (concorrencia["cnpj_concorrente"]
                                        .str.replace(r"\D", "", regex=True))
    return {"coleta_1fn": coleta_1fn,
            "posto_servico_1fn": posto_servico,
            "gerente_telefone_1fn": telefones,
            "concorrencia_1fn": concorrencia.rename(
                columns={"cnpj": "cnpj_proprio"})}


# ----------------------------------------------------------- etapa 2: 2FN
def aplicar_2fn(t1: dict) -> dict:
    """Chave de coleta_1fn: (cnpj, data_coleta, produto).
    - produto -> unidade_medida                 (depende so de 'produto')
    - cnpj -> dados cadastrais do posto          (depende so de 'cnpj')
    - (cnpj, data) -> bandeira, semana, obs.     (nao depende de 'produto')
    - (cnpj, data, produto) -> valor_venda       (dependencia total: fica)
    As relacoes auxiliares da 1FN perdem as linhas repetidas."""
    c = t1["coleta_1fn"]
    # Anomalia de atualizacao herdada: apos a troca, parte das linhas ainda
    # traz o gerente antigo. Regra de negocio adotada: o gerente vigente e
    # o que apareceu por ultimo na historia do posto (maior 1a aparicao).
    estreia = (c.dropna(subset=["gerente"])
               .groupby(["cnpj", "gerente"])["data_coleta"].min()
               .reset_index().sort_values("data_coleta"))
    vigente = estreia.drop_duplicates("cnpj", keep="last")
    c = c.drop(columns="gerente").merge(
        vigente[["cnpj", "gerente"]], on="cnpj", how="left")
    produto = c[["produto", "unidade_medida"]].drop_duplicates()
    posto = c[["cnpj", "tipo_posto", "razao_social", "grupo_economico",
               "logradouro", "numero", "complemento", "bairro", "cep",
               "municipio", "uf", "regiao", "gerente"]].drop_duplicates(
                   subset="cnpj", keep="last")
    coleta = c[["cnpj", "data_coleta", "bandeira", "semana_ref",
                "observacoes"]].drop_duplicates(subset=["cnpj",
                                                        "data_coleta"])
    item = c[["cnpj", "data_coleta", "produto", "valor_venda"]]
    return {"posto_2fn": posto, "produto_2fn": produto,
            "coleta_2fn": coleta, "item_coleta_2fn": item,
            "posto_servico_2fn": t1["posto_servico_1fn"].drop_duplicates(),
            "gerente_telefone_2fn":
                t1["gerente_telefone_1fn"].drop_duplicates(),
            "concorrencia_2fn": t1["concorrencia_1fn"].drop_duplicates()}


# ----------------------------------------------------------- etapa 3: 3FN
def criar_ids(valores: pd.Series, prefixo: str) -> pd.DataFrame:
    """Cria chave substituta sequencial para um dominio de valores."""
    unicos = sorted(valores.dropna().unique())
    return pd.DataFrame({f"id_{prefixo}": range(1, len(unicos) + 1),
                         "nome": unicos})


def aplicar_3fn(t2: dict) -> dict:
    """Remove dependencias transitivas:
    - cnpj -> municipio -> uf -> regiao
    - cnpj -> cnpj_raiz -> grupo_economico
    - cnpj -> gerente (nome/telefones sao do gerente, nao do posto)
    - (cnpj, data) -> data -> semana_ref (atributo derivado: vira calculo)
    Dominios textuais (bandeira, servico, produto) ganham tabelas proprias
    para garantir integridade de dominio via FOREIGN KEY."""
    posto = t2["posto_2fn"].copy()
    coleta = t2["coleta_2fn"].copy()

    regiao = pd.DataFrame({"sigla_regiao": sorted(posto["regiao"].unique())})
    regiao["nome"] = regiao["sigla_regiao"].map(REGIOES)
    uf = (posto[["uf", "regiao"]].drop_duplicates()
          .rename(columns={"uf": "sigla_uf", "regiao": "sigla_regiao"}))
    municipio = (posto[["municipio", "uf"]].drop_duplicates()
                 .sort_values("municipio").reset_index(drop=True))
    municipio.insert(0, "id_municipio", municipio.index + 1)
    municipio.columns = ["id_municipio", "nome", "sigla_uf"]

    posto["cnpj_raiz"] = posto["cnpj"].str[:8]
    grupo = (posto[["cnpj_raiz", "grupo_economico"]]
             .drop_duplicates(subset="cnpj_raiz")
             .rename(columns={"grupo_economico": "nome"}))

    gerente = criar_ids(t2["gerente_telefone_2fn"]["gerente"], "gerente")
    telefone = t2["gerente_telefone_2fn"].merge(
        gerente, left_on="gerente", right_on="nome")[["id_gerente",
                                                      "telefone"]]

    posto = posto.merge(municipio, left_on=["municipio", "uf"],
                        right_on=["nome", "sigla_uf"])
    posto = posto.merge(gerente.rename(columns={"nome": "gerente"}),
                        on="gerente", how="left")
    posto["id_gerente"] = posto["id_gerente"].astype("Int64")
    posto = posto[["cnpj", "razao_social", "tipo_posto", "cnpj_raiz",
                   "logradouro", "numero", "complemento", "bairro", "cep",
                   "id_municipio", "id_gerente"]]

    servico = criar_ids(t2["posto_servico_2fn"]["servico"], "servico")
    posto_servico = t2["posto_servico_2fn"].merge(
        servico, left_on="servico", right_on="nome")[["cnpj", "id_servico"]]

    produto = criar_ids(t2["produto_2fn"]["produto"], "produto").merge(
        t2["produto_2fn"], left_on="nome", right_on="produto")
    produto = produto[["id_produto", "nome", "unidade_medida"]]

    bandeira = criar_ids(coleta["bandeira"], "bandeira")
    coleta = coleta.merge(bandeira, left_on="bandeira", right_on="nome")
    coleta = coleta.sort_values(["data_coleta", "cnpj"]).reset_index(
        drop=True)
    coleta.insert(0, "id_coleta", coleta.index + 1)

    item = (t2["item_coleta_2fn"]
            .merge(coleta[["id_coleta", "cnpj", "data_coleta"]],
                   on=["cnpj", "data_coleta"])
            .merge(produto, left_on="produto", right_on="nome"))
    item = item[["id_coleta", "id_produto", "valor_venda"]]

    coleta = coleta[["id_coleta", "cnpj", "data_coleta", "id_bandeira",
                     "observacoes"]].rename(
                         columns={"observacoes": "observacao"})
    return {"regiao": regiao, "uf": uf, "municipio": municipio,
            "grupo_economico": grupo, "gerente": gerente,
            "telefone_gerente": telefone, "posto": posto,
            "servico": servico, "posto_servico": posto_servico,
            "concorrencia": t2["concorrencia_2fn"], "produto": produto,
            "bandeira": bandeira, "coleta": coleta, "item_coleta": item}


# ---------------------------------------------------------------- validacao
def validar_endereco(posto: pd.DataFrame, caminho_anp: str) -> None:
    """Confere a decomposicao do endereco contra a base original da ANP."""
    anp = pd.read_csv(caminho_anp, sep=";", dtype=str)
    campos = ["nome_da_rua", "numero_rua", "complemento", "bairro"]
    originais = set(anp[campos].fillna("").astype(str)
                    .apply(tuple, axis=1))
    campos_3fn = ["logradouro", "numero", "complemento", "bairro"]
    obtidos = posto[campos_3fn].fillna("").astype(str).apply(tuple, axis=1)
    acertos = obtidos.isin(originais).sum()
    print(f"\nValidacao do endereco: {acertos}/{len(posto)} postos "
          f"decompostos exatamente como na ANP.")
    erros = posto[~obtidos.isin(originais)]
    if not erros.empty:
        print(erros[["cnpj"] + campos_3fn].to_string(index=False))


def main() -> None:
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        sys.exit(1)
    bruto = pd.read_csv(sys.argv[1], sep=";", dtype=str,
                        encoding="utf-8-sig")
    salvar({"planilha_caotica": bruto}, "0_original")
    limpo = limpar(bruto)
    salvar({"planilha_limpa": limpo}, "0_limpeza")
    t1 = aplicar_1fn(limpo)
    salvar(t1, "1fn")
    t2 = aplicar_2fn(t1)
    salvar(t2, "2fn")
    t3 = aplicar_3fn(t2)
    salvar(t3, "3fn")
    total = sum(t.size for t in t3.values())
    print(f"\nCelulas: original={bruto.size} | 3FN={total}")
    if len(sys.argv) == 3:
        validar_endereco(t3["posto"], sys.argv[2])


if __name__ == "__main__":
    main()
