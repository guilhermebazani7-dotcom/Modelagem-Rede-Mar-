"""
01_recorte_anp.py
-----------------
Recorta a Serie Historica de Precos de Combustiveis (ANP) para uma UF
e gera um perfil rapido dos dados (evidencias de redundancia e sujeira).

Uso:
    python 01_recorte_anp.py <arquivo_anp.csv> <UF>
Exemplo:
    python 01_recorte_anp.py ca-2026-01.csv ES

Saida:
    anp_recorte_<UF>.csv  -> base real recortada (entrada das proximas fases)
"""
import sys
import unicodedata

import pandas as pd


def normalizar_coluna(nome: str) -> str:
    """Converte 'CNPJ da Revenda' -> 'cnpj_da_revenda' (sem acentos)."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore")
    texto = sem_acento.decode().strip().lower()
    return "_".join(texto.replace("-", " ").split())


def ler_csv_anp(caminho: str) -> pd.DataFrame:
    """Le o CSV da ANP (separador ';', decimal ','), testando encodings."""
    for encoding in ("utf-8", "latin-1"):
        try:
            df = pd.read_csv(caminho, sep=";", decimal=",", dtype=str,
                             encoding=encoding)
            df.columns = [normalizar_coluna(c) for c in df.columns]
            return df
        except UnicodeDecodeError:
            continue
    raise ValueError("Nao foi possivel ler o arquivo com utf-8 ou latin-1.")


def perfilar(df: pd.DataFrame) -> None:
    """Imprime indicadores que alimentam o diagnostico (Fase 1)."""
    print(f"\nColunas: {list(df.columns)}")
    print(f"Linhas no recorte: {len(df):,}")
    print(f"Postos distintos (CNPJ): {df['cnpj_da_revenda'].nunique():,}")
    print(f"Municipios distintos: {df['municipio'].nunique():,}")
    print(f"Produtos: {sorted(df['produto'].dropna().unique())}")

    nomes = df.groupby("cnpj_da_revenda")["revenda"].nunique()
    print(f"CNPJs com MAIS DE UM nome de revenda: {(nomes > 1).sum():,}")

    bandeiras = df.groupby("cnpj_da_revenda")["bandeira"].nunique()
    print(f"CNPJs com MAIS DE UMA bandeira: {(bandeiras > 1).sum():,}")

    unidades = df.groupby("produto")["unidade_de_medida"].unique()
    print("\nUnidade de medida por produto (candidata a dep. parcial):")
    print(unidades.to_string())

    # Redundancia: quantas vezes os dados cadastrais de um posto se repetem
    repeticoes = df.groupby("cnpj_da_revenda").size()
    print(f"\nMedia de repeticoes do cadastro por posto: "
          f"{repeticoes.mean():.1f} linhas")


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    caminho, uf = sys.argv[1], sys.argv[2].upper()
    df = ler_csv_anp(caminho)
    recorte = df[df["estado_sigla"] == uf].copy()

    if recorte.empty:
        print(f"Nenhuma linha para UF={uf}. Siglas: "
              f"{sorted(df['estado_sigla'].dropna().unique())}")
        sys.exit(1)

    perfilar(recorte)
    saida = f"anp_recorte_{uf}.csv"
    recorte.to_csv(saida, sep=";", index=False, encoding="utf-8")
    print(f"\nArquivo gerado: {saida}")


if __name__ == "__main__":
    main()
