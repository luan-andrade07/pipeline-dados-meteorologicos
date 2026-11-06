
import pandas as pd

from src.logging_config import logger


def validar_tratar_dados(df):
    """Valida os dados e remove registros inconsistentes."""

    if df is None or df.empty:
        logger.warning("Nenhum dado disponível para validação.")
        return None

    colunas_obrigatorias = [
        "cidade",
        "estado",
        "data_referencia",
        "temperatura_max_c",
        "temperatura_min_c",
        "precipitacao_mm",
        "umidade_media_pct",
        "vento_max_kmh",
        "codigo_clima"
    ]

    colunas_ausentes = [
        coluna
        for coluna in colunas_obrigatorias
        if coluna not in df.columns
    ]

    if colunas_ausentes:
        logger.error(
            "Colunas obrigatórias ausentes: %s",
            colunas_ausentes
        )
        return None

    df = df.copy()

    # Padronização dos textos
    df["cidade"] = df["cidade"].astype("string").str.strip()

    df["estado"] = (
        df["estado"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    # Conversão da data
    df["data_referencia"] = pd.to_datetime(
        df["data_referencia"],
        errors="coerce"
    )

    # Conversão dos campos numéricos
    colunas_numericas = [
        "temperatura_max_c",
        "temperatura_min_c",
        "precipitacao_mm",
        "umidade_media_pct",
        "vento_max_kmh",
        "codigo_clima"
    ]

    conversao_invalida = pd.Series(
        False,
        index=df.index
    )

    for coluna in colunas_numericas:

        original = df[coluna].copy()

        df[coluna] = pd.to_numeric(
            df[coluna],
            errors="coerce"
        )

        conversao_invalida |= (
            original.notna() & df[coluna].isna()
        )

    # Regras de qualidade dos dados
    motivos_invalidade = {

        "Data inválida": (
            df["data_referencia"].isna()
        ),

        "Cidade ou estado ausente": (
            df["cidade"].isna()
            | df["cidade"].eq("").fillna(True)
            | df["estado"].isna()
            | df["estado"].eq("").fillna(True)
        ),

        "Valor numérico inválido": (
            conversao_invalida
        ),

        "Temperatura máxima fora do intervalo": (
            df["temperatura_max_c"].notna()
            & ~df["temperatura_max_c"].between(-90, 60)
        ),

        "Temperatura mínima fora do intervalo": (
            df["temperatura_min_c"].notna()
            & ~df["temperatura_min_c"].between(-90, 60)
        ),

        "Temperatura mínima maior que máxima": (
            df["temperatura_min_c"].notna()
            & df["temperatura_max_c"].notna()
            & (
                df["temperatura_min_c"]
                > df["temperatura_max_c"]
            )
        ),

        "Precipitação negativa": (
            df["precipitacao_mm"].notna()
            & (df["precipitacao_mm"] < 0)
        ),

        "Umidade fora do intervalo": (
            df["umidade_media_pct"].notna()
            & ~df["umidade_media_pct"].between(0, 100)
        ),

        "Velocidade do vento negativa": (
            df["vento_max_kmh"].notna()
            & (df["vento_max_kmh"] < 0)
        ),

        "Código climático inválido": (
            df["codigo_clima"].notna()
            & (
                (df["codigo_clima"] < 0)
                | (df["codigo_clima"] % 1 != 0)
            )
        )
    }

    registros_invalidos = pd.Series(
        False,
        index=df.index
    )

    for motivo, mascara in motivos_invalidade.items():

        quantidade = int(mascara.sum())

        if quantidade > 0:
            logger.warning(
                "%s: %d registro(s).",
                motivo,
                quantidade
            )

        registros_invalidos |= mascara

    quantidade_invalida = int(
        registros_invalidos.sum()
    )

    # Remove os registros inválidos
    df = df.loc[~registros_invalidos].copy()

    # Remove duplicidades dentro da coleta
    duplicados = df.duplicated(
        subset=[
            "cidade",
            "estado",
            "data_referencia"
        ]
    ).sum()

    df = df.drop_duplicates(
        subset=[
            "cidade",
            "estado",
            "data_referencia"
        ],
        keep="last"
    )

    # Identifica valores ausentes
    for coluna in colunas_numericas:

        ausentes = int(df[coluna].isna().sum())

        if ausentes > 0:
            logger.warning(
                "%d valor(es) ausente(s) em %s.",
                ausentes,
                coluna
            )

    if df.empty:
        logger.error("Nenhum registro válido após a validação.")
        return None

    # Formata a data para o banco de dados
    df["data_referencia"] = (
        df["data_referencia"].dt.strftime("%Y-%m-%d")
    )

    logger.info(
        "Validação concluída. Recebidos: %d | Inválidos: %d | "
        "Duplicados: %d | Válidos: %d",
        len(registros_invalidos),
        quantidade_invalida,
        duplicados,
        len(df)
    )

    return df
