
from typing import Optional

import numpy as np
import pandas as pd

from src.logging_config import logger


# Colunas obrigatórias para o funcionamento do pipeline
COLUNAS_OBRIGATORIAS = [
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

# Campos que devem conter valores numéricos
COLUNAS_NUMERICAS = [
    "temperatura_max_c",
    "temperatura_min_c",
    "precipitacao_mm",
    "umidade_media_pct",
    "vento_max_kmh",
    "codigo_clima"
]

# Intervalos de validação
TEMPERATURA_MINIMA = -90
TEMPERATURA_MAXIMA = 60

UMIDADE_MINIMA = 0
UMIDADE_MAXIMA = 100

# Identificação única de cada previsão
CHAVE_UNICA = [
    "cidade",
    "estado",
    "data_referencia"
]


def validar_tratar_dados(
    df: Optional[pd.DataFrame]
) -> Optional[pd.DataFrame]:
    """
    Valida, padroniza e transforma os dados meteorológicos.

    Args:
        df: DataFrame recebido da etapa de extração.

    Returns:
        DataFrame com registros válidos ou None quando
        não houver dados suficientes para processamento.
    """

    # Verifica se existem dados para processar
    if df is None or not isinstance(df, pd.DataFrame):
        logger.warning("Dados recebidos em formato inválido.")
        return None

    if df.empty:
        logger.warning("Nenhum dado disponível para validação.")
        return None

    quantidade_recebida = len(df)

    logger.info(
        "Iniciando validação de %d registros.",
        quantidade_recebida
    )

    # Verifica a existência das colunas obrigatórias
    colunas_ausentes = [
        coluna
        for coluna in COLUNAS_OBRIGATORIAS
        if coluna not in df.columns
    ]

    if colunas_ausentes:
        logger.error(
            "Colunas obrigatórias ausentes: %s",
            colunas_ausentes
        )
        return None

    # Trabalha com uma cópia para não modificar os dados originais
    df = df.copy()

    # Padronização dos campos textuais
    for coluna in ["cidade", "estado"]:
        df[coluna] = (
            df[coluna]
            .astype("string")
            .str.strip()
        )

    df["estado"] = df["estado"].str.upper()

    # Conversão e validação das datas
    df["data_referencia"] = pd.to_datetime(
        df["data_referencia"],
        errors="coerce"
    )

    # Identifica valores numéricos inválidos
    conversao_invalida = pd.Series(
        False,
        index=df.index,
        dtype=bool
    )

    for coluna in COLUNAS_NUMERICAS:

        valor_original = df[coluna].copy()

        df[coluna] = pd.to_numeric(
            df[coluna],
            errors="coerce"
        )

        conversao_invalida |= (
            valor_original.notna()
            & df[coluna].isna()
        )

    # Identifica valores infinitos
    valores_nao_finitos = pd.Series(
        False,
        index=df.index,
        dtype=bool
    )

    for coluna in COLUNAS_NUMERICAS:

        valores_presentes = df[coluna].notna()

        valores_nao_finitos |= (
            valores_presentes
            & ~np.isfinite(df[coluna].astype(float))
        )

    # Define as regras de qualidade
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

        "Conversão numérica inválida": (
            conversao_invalida
        ),

        "Valor numérico infinito": (
            valores_nao_finitos
        ),

        "Temperatura máxima fora do intervalo": (
            df["temperatura_max_c"].notna()
            & ~df["temperatura_max_c"].between(
                TEMPERATURA_MINIMA,
                TEMPERATURA_MAXIMA
            )
        ),

        "Temperatura mínima fora do intervalo": (
            df["temperatura_min_c"].notna()
            & ~df["temperatura_min_c"].between(
                TEMPERATURA_MINIMA,
                TEMPERATURA_MAXIMA
            )
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
            & ~df["umidade_media_pct"].between(
                UMIDADE_MINIMA,
                UMIDADE_MAXIMA
            )
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

    # Consolida os registros que apresentam inconsistências
    registros_invalidos = pd.Series(
        False,
        index=df.index,
        dtype=bool
    )

    for motivo, mascara in motivos_invalidade.items():

        quantidade = int(mascara.sum())

        if quantidade > 0:

            logger.warning(
                "%s: %d registro(s) encontrado(s).",
                motivo,
                quantidade
            )

        registros_invalidos |= mascara

    quantidade_invalida = int(
        registros_invalidos.sum()
    )

    # Remove os registros inválidos
    df = df.loc[~registros_invalidos].copy()

    # Remove duplicidades considerando a chave única
    quantidade_duplicados = int(
        df.duplicated(subset=CHAVE_UNICA).sum()
    )

    df = df.drop_duplicates(
        subset=CHAVE_UNICA,
        keep="last"
    )

    # Identifica valores ausentes nas medições
    for coluna in COLUNAS_NUMERICAS:

        quantidade_ausente = int(
            df[coluna].isna().sum()
        )

        if quantidade_ausente > 0:

            logger.warning(
                "%d valor(es) ausente(s) na coluna %s.",
                quantidade_ausente,
                coluna
            )

    # Interrompe caso nenhum registro seja válido
    if df.empty:
        logger.error(
            "Nenhum registro válido após a transformação."
        )
        return None

    # Padroniza as datas para armazenamento no MySQL
    df["data_referencia"] = (
        df["data_referencia"]
        .dt.strftime("%Y-%m-%d")
    )

    # Organiza o índice final
    df = df.reset_index(drop=True)

    # Registra o resultado da transformação
    logger.info(
        "Validação concluída. "
        "Recebidos: %d | "
        "Inválidos: %d | "
        "Duplicados: %d | "
        "Válidos: %d",
        quantidade_recebida,
        quantidade_invalida,
        quantidade_duplicados,
        len(df)
    )

    return df
