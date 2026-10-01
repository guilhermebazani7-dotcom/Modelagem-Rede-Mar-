"""
02_gerador_planilha_caotica.py
------------------------------
Gera a "planilha monstro" da Rede Mare Combustiveis a partir do recorte REAL
da Serie Historica de Precos da ANP (anp_recorte_ES.csv).

Narrativa: o analista de pricing da Rede Mare (grupo capixaba de bandeira
branca, 5 postos na Grande Vitoria) consolida semanalmente os precos da ANP
numa planilha compartilhada e acrescenta colunas proprias (concorrentes,
servicos, gerente). O resultado e uma tabela universal desnormalizada.

O que e REAL (vem da ANP): postos concorrentes, enderecos, bandeiras, produtos,
datas e precos de venda. Sujeiras reais preservadas: espaco antes do CNPJ,
numeros "S/N", complementos vazios, trocas de bandeira ao longo do semestre.

O que e SIMULADO (injetado de forma controlada, seed fixa):
  [1FN] Produtos, precos e unidades agrupados numa unica celula por coleta.
  [1FN] Endereco composto (rua, numero, complemento, bairro) numa so coluna.
  [1FN] Servicos, telefones e concorrentes como listas com separadores mistos.
  [ANON] Os 5 postos da Rede Mare sao postos reais de bandeira branca com
         CNPJ e razao social substituidos por dados ficticios.
  [ANOMALIA] Troca de gerente atualizada so em parte das linhas.
  [FORMATO] Variacoes de grafia (razao social, municipio, unidade, CNPJ sem
            mascara, datas ISO), linhas duplicadas e observacoes livres.

Uso:
    python 02_gerador_planilha_caotica.py anp_recorte_ES.csv
Saida:
    planilha_caotica.csv   -> tabela universal (entrada da normalizacao)
    metricas_baseline.json -> KPIs do "antes" para o relatorio
"""
import json
import random
import sys

import pandas as pd

SEED = 42
GRANDE_VITORIA = ["VITORIA", "VILA VELHA", "SERRA", "CARIACICA"]
RAIZ_MARE = "11222333"
RAZAO_MARE = "REDE MARE COMBUSTIVEIS LTDA"
DATA_TROCA_GERENTE = pd.Timestamp("2026-04-15")
TAXA_ATUALIZACAO_GERENTE = 0.6  # so 60% das linhas foram corrigidas

CATALOGO_SERVICOS = ["Conveniencia", "Troca de oleo", "Lava-jato",
                     "Calibragem", "Caixa eletronico", "Borracharia"]
GERENTES_MARE = [
    ("Carlos Menezes", "(27) 99811-2041 / (27) 3334-1100"),
    ("Juliana Rocha", "(27) 99702-3355"),
    ("Paulo Ferraz", "(27) 99945-7810 / (27) 3226-4410"),
    ("Renata Alves", "(27) 99633-9021"),
    ("Marcos Lyrio", "(27) 99890-1276 / (27) 3345-0098"),
]
NOVO_GERENTE = ("Fernanda Castro", "(27) 99720-4488")
OBSERVACOES = ["preco conferido por telefone", "ATUALIZAR!!",
               "ver com gerente", "promo fim de semana?", "conferir bandeira"]


def calcular_dv_cnpj(base12: str) -> str:
    """Calcula os 2 digitos verificadores de um CNPJ (12 digitos base)."""
    def digito(numeros: str, pesos: list) -> str:
        soma = sum(int(n) * p for n, p in zip(numeros, pesos))
        resto = soma % 11
        return "0" if resto < 2 else str(11 - resto)

    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    dv1 = digito(base12, pesos1)
    dv2 = digito(base12 + dv1, [6] + pesos1)
    return dv1 + dv2


def formatar_cnpj(digitos: str) -> str:
    """'11222333000181' -> '11.222.333/0001-81'."""
    d = digitos
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def selecionar_postos_mare(df: pd.DataFrame) -> list:
    """Escolhe 5 postos reais de bandeira branca na Grande Vitoria:
    o de maior historico em cada municipio + o proximo melhor geral."""
    gv = df[df["municipio"].isin(GRANDE_VITORIA)]
    resumo = gv.groupby("cnpj_da_revenda").agg(
        bandeiras=("bandeira", lambda s: set(s)),
        coletas=("produto", "size"),
        municipio=("municipio", "first"),
    )
    brancos = resumo[resumo["bandeiras"] == {"BRANCA"}]
    brancos = brancos.sort_values(["coletas"], ascending=False)
    escolhidos = brancos.groupby("municipio").head(1).index.tolist()
    extra = [c for c in brancos.index if c not in escolhidos][0]
    return escolhidos + [extra]


def anonimizar_mare(df: pd.DataFrame, postos: list) -> dict:
    """Substitui CNPJ/razao social dos postos escolhidos por dados ficticios.
    Retorna o mapa CNPJ real -> CNPJ ficticio."""
    mapa = {}
    for i, cnpj_real in enumerate(postos, start=1):
        base = f"{RAIZ_MARE}{i:04d}"
        mapa[cnpj_real] = " " + formatar_cnpj(base + calcular_dv_cnpj(base))
    filtro = df["cnpj_da_revenda"].isin(postos)
    df.loc[filtro, "revenda"] = RAZAO_MARE
    df["cnpj_da_revenda"] = df["cnpj_da_revenda"].replace(mapa)
    return mapa


def montar_endereco(linha: pd.Series) -> str:
    """Junta as partes do endereco numa unica string (atributo composto)."""
    partes = [f"{linha['nome_da_rua']}, {linha['numero_rua']}"]
    if pd.notna(linha["complemento"]):
        partes.append(str(linha["complemento"]))
    partes.append(str(linha["bairro"]))
    return " - ".join(partes)


def agrupar_por_coleta(df: pd.DataFrame) -> pd.DataFrame:
    """1 linha por (posto, data): produtos/precos/unidades viram listas."""
    df = df.sort_values(["cnpj_da_revenda", "data", "produto"])
    df["preco_txt"] = df["valor_de_venda"].str.replace(".", ",", regex=False)
    chaves = ["cnpj_da_revenda", "data"]
    agrupado = df.groupby(chaves, as_index=False).agg(
        razao_social=("revenda", "first"),
        bandeira=("bandeira", "first"),
        endereco=("endereco", "first"),
        cep=("cep", "first"),
        municipio=("municipio", "first"),
        uf=("estado_sigla", "first"),
        regiao=("regiao_sigla", "first"),
        produtos=("produto", ", ".join),
        precos=("preco_txt", " / ".join),
        unidades=("unidade_de_medida", "; ".join),
    )
    return agrupado


def definir_grupo_economico(df: pd.DataFrame) -> pd.Series:
    """CNPJ -> raiz (8 digitos) -> grupo. Dependencia transitiva proposital."""
    raiz = df["cnpj_da_revenda"].str.replace(r"\D", "", regex=True).str[:8]
    nome_por_raiz = df.groupby(raiz)["razao_social"].agg(
        lambda s: s.mode().iloc[0])
    grupo = raiz.map(nome_por_raiz)
    return grupo.where(raiz != RAIZ_MARE, "REDE MARE")


def definir_concorrentes(df: pd.DataFrame, cnpjs_mare: list) -> dict:
    """Para cada posto Mare, os 3 concorrentes com mais coletas no municipio.
    Postos Mare no mesmo municipio compartilham concorrentes (N:M)."""
    outros = df[~df["cnpj_da_revenda"].isin(cnpjs_mare)]
    ranking = (outros.groupby(["municipio", "cnpj_da_revenda"]).size()
               .reset_index(name="n")
               .sort_values(["municipio", "n"], ascending=[True, False]))
    concorrentes = {}
    for cnpj in cnpjs_mare:
        mun = df.loc[df["cnpj_da_revenda"] == cnpj, "municipio"].iloc[0]
        top = ranking[ranking["municipio"] == mun].head(3)
        concorrentes[cnpj] = [c.strip() for c in top["cnpj_da_revenda"]]
    return concorrentes


def injetar_colunas_do_analista(df: pd.DataFrame, cnpjs_mare: list,
                                rng: random.Random) -> pd.DataFrame:
    """Acrescenta as colunas 'da empresa' que misturam contextos."""
    df["tipo_posto"] = df["cnpj_da_revenda"].isin(cnpjs_mare).map(
        {True: "PROPRIO", False: "CONCORRENTE"})
    df["semana_ref"] = df["data"].dt.strftime("%G-S%V")

    servicos_posto = {c: rng.sample(CATALOGO_SERVICOS, rng.randint(1, 4))
                      for c in df["cnpj_da_revenda"].unique()}
    separadores = [", ", "; ", " / ", ","]
    df["servicos"] = [rng.choice(separadores).join(servicos_posto[c])
                      for c in df["cnpj_da_revenda"]]

    gerente_por_posto = dict(zip(cnpjs_mare, GERENTES_MARE))
    concorrentes = definir_concorrentes(df, cnpjs_mare)
    gerentes, telefones, lista_conc = [], [], []
    for _, linha in df.iterrows():
        cnpj = linha["cnpj_da_revenda"]
        if cnpj not in gerente_por_posto:
            gerentes.append(None)
            telefones.append(None)
            lista_conc.append(None)
            continue
        nome, fone = gerente_por_posto[cnpj]
        trocou = (cnpj == cnpjs_mare[0]
                  and linha["data"] >= DATA_TROCA_GERENTE
                  and rng.random() < TAXA_ATUALIZACAO_GERENTE)
        if trocou:
            nome, fone = NOVO_GERENTE
        gerentes.append(nome)
        telefones.append(fone)
        lista_conc.append(rng.choice(["; ", " / "]).join(concorrentes[cnpj]))
    df["gerente"] = gerentes
    df["telefones_gerente"] = telefones
    df["concorrentes_diretos"] = lista_conc
    return df


def variar_texto(serie: pd.Series, taxa: float, variacoes: dict,
                 rng: random.Random) -> pd.Series:
    """Aplica variacoes de grafia em uma fracao das linhas."""
    def trocar(valor):
        if valor in variacoes and rng.random() < taxa:
            return rng.choice(variacoes[valor])
        return valor
    return serie.map(trocar)


def injetar_sujeira_de_formato(df: pd.DataFrame,
                               rng: random.Random) -> pd.DataFrame:
    """Sujeiras tipicas de digitacao manual (nao sao violacoes de FN)."""
    nomes = {n: [n.title(), n.replace(" LTDA", ""), n.replace("LTDA", "LTDA.")]
             for n in df["razao_social"].unique()}
    df["razao_social"] = variar_texto(df["razao_social"], 0.06, nomes, rng)

    municipios = {"VITORIA": ["Vitoria", "VITÓRIA", "Vitória"],
                  "VILA VELHA": ["V. VELHA", "Vila Velha"],
                  "CARIACICA": ["Cariacica"], "SERRA": ["Serra "]}
    df["municipio"] = variar_texto(df["municipio"], 0.05, municipios, rng)

    df["unidades"] = [u.replace("R$ / litro", "R$/l")
                      if rng.random() < 0.05 else u for u in df["unidades"]]

    df["cnpj"] = [c.strip().replace(".", "").replace("/", "").replace("-", "")
                  if rng.random() < 0.04 else c
                  for c in df["cnpj_da_revenda"]]

    df["data_coleta"] = [d.strftime("%Y-%m-%d") if rng.random() < 0.03
                         else d.strftime("%d/%m/%Y") for d in df["data"]]

    df["observacoes"] = [rng.choice(OBSERVACOES) if rng.random() < 0.04
                         else None for _ in range(len(df))]

    duplicadas = df.sample(n=10, random_state=SEED)
    return pd.concat([df, duplicadas], ignore_index=True)


def calcular_metricas(df: pd.DataFrame, cnpjs_mare: list) -> dict:
    """KPIs do cenario 'antes' (baseline) para o relatorio executivo."""
    cnpj_limpo = df["cnpj"].str.replace(r"\D", "", regex=True)
    colunas_cadastro = ["razao_social", "grupo_economico", "endereco", "cep",
                        "municipio", "uf", "regiao", "servicos"]
    linhas_por_posto = cnpj_limpo.value_counts()
    celulas_redundantes = int(((linhas_por_posto - 1)
                               * len(colunas_cadastro)).sum())
    variantes_nome = df.groupby(cnpj_limpo)["razao_social"].nunique()
    posto_troca = cnpjs_mare[0].replace(".", "").replace("/", "")
    posto_troca = posto_troca.replace("-", "").strip()
    apos_troca = df[(cnpj_limpo == posto_troca)
                    & (df["data"] >= DATA_TROCA_GERENTE)]
    multivaloradas = df["produtos"].str.contains(",").sum()

    return {
        "linhas": int(len(df)),
        "colunas": int(df.shape[1]),
        "postos_distintos": int(cnpj_limpo.nunique()),
        "celulas_cadastrais_redundantes": celulas_redundantes,
        "cnpjs_com_mais_de_uma_grafia_de_nome": int(
            (variantes_nome > 1).sum()),
        "linhas_a_editar_se_gerente_mudar": int(len(apos_troca)),
        "linhas_com_gerente_desatualizado": int(
            (apos_troca["gerente"] != NOVO_GERENTE[0]).sum()),
        "linhas_com_produtos_multivalorados": int(multivaloradas),
        "linhas_duplicadas": int(df.duplicated().sum()),
    }


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    rng = random.Random(SEED)

    df = pd.read_csv(sys.argv[1], sep=";", dtype=str)
    df["data"] = pd.to_datetime(df["data_da_coleta"], dayfirst=True)
    df["endereco"] = df.apply(montar_endereco, axis=1)

    postos_reais = selecionar_postos_mare(df)
    mapa = anonimizar_mare(df, postos_reais)
    df.loc[df["cnpj_da_revenda"].isin(mapa.values()), "bandeira"] = "BRANCA"
    cnpjs_mare = list(mapa.values())

    planilha = agrupar_por_coleta(df)
    planilha["grupo_economico"] = definir_grupo_economico(planilha)
    planilha = injetar_colunas_do_analista(planilha, cnpjs_mare, rng)
    planilha = injetar_sujeira_de_formato(planilha, rng)

    colunas_finais = [
        "data_coleta", "semana_ref", "tipo_posto", "cnpj", "razao_social",
        "grupo_economico", "bandeira", "endereco", "cep", "municipio", "uf",
        "regiao", "produtos", "precos", "unidades", "servicos", "gerente",
        "telefones_gerente", "concorrentes_diretos", "observacoes",
    ]
    metricas = calcular_metricas(planilha, cnpjs_mare)
    metricas["colunas"] = len(colunas_finais)
    planilha = planilha.sort_values(["data", "cnpj_da_revenda"])
    planilha[colunas_finais].to_csv("planilha_caotica.csv", sep=";",
                                    index=False, encoding="utf-8-sig")
    with open("metricas_baseline.json", "w", encoding="utf-8") as arquivo:
        json.dump(metricas, arquivo, indent=2, ensure_ascii=False)

    print("Postos da Rede Mare (real -> ficticio):")
    for real, ficticio in mapa.items():
        print(f"  {real.strip()} -> {ficticio.strip()}")
    print("\nMetricas baseline:")
    print(json.dumps(metricas, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
