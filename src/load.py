
import os
from typing import Dict, Optional

import pandas as pd

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine
from sqlalchemy.exc import SQLAlchemyError

from src.logging_config import logger


# Configurações obrigatórias do banco
VARIAVEIS_AMBIENTE = [
    "MYSQL_HOST",
    "MYSQL_PORT",
    "MYSQL_DATABASE",
    "MYSQL_USER",
    "MYSQL_PASSWORD"
]

# Colunas necessárias para a gravação
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


def obter_configuracoes_banco() -> Dict[str, str]:
    """Obtém e valida as configurações do banco de dados."""

    configuracoes = {
        chave: os.getenv(chave)
        for chave in VARIAVEIS_AMBIENTE
    }

    variaveis_ausentes = [
        chave
        for chave, valor in configuracoes.items()
        if not valor
    ]

    if variaveis_ausentes:
        raise ValueError(
            "Configurações ausentes no arquivo .env: "
            f"{variaveis_ausentes}"
        )

    try:
        porta = int(configuracoes["MYSQL_PORT"])
    except ValueError as erro:
        raise ValueError(
            "A porta MYSQL_PORT precisa ser um número inteiro."
        ) from erro

    if not 1 <= porta <= 65535:
        raise ValueError(
            "A porta do MySQL precisa estar entre 1 e 65535."
        )

    configuracoes["MYSQL_PORT"] = str(porta)

    return configuracoes


def criar_conexao() -> Engine:
    """Cria uma conexão com o banco de dados MySQL."""

    configuracoes = obter_configuracoes_banco()

    url = URL.create(
        drivername="mysql+pymysql",
        username=configuracoes["MYSQL_USER"],
        password=configuracoes["MYSQL_PASSWORD"],
        host=configuracoes["MYSQL_HOST"],
        port=int(configuracoes["MYSQL_PORT"]),
        database=configuracoes["MYSQL_DATABASE"]
    )

    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=3600,
        connect_args={
            "connect_timeout": 10
        }
    )

    logger.info(
        "Configuração da conexão MySQL preparada para o banco %s.",
        configuracoes["MYSQL_DATABASE"]
    )

    return engine


def preparar_registros(df: pd.DataFrame) -> list:
    """Prepara os dados para inserção no MySQL."""

    colunas_ausentes = [
        coluna
        for coluna in COLUNAS_OBRIGATORIAS
        if coluna not in df.columns
    ]

    if colunas_ausentes:
        raise ValueError(
            f"Colunas ausentes para gravação: {colunas_ausentes}"
        )

    dados = df[COLUNAS_OBRIGATORIAS].copy()

    # Valida e converte as datas
    dados["data_referencia"] = pd.to_datetime(
        dados["data_referencia"],
        errors="raise"
    ).dt.date

    # Converte valores ausentes para None,
    # compatível com os parâmetros enviados ao MySQL
    dados = dados.astype(object).where(
        pd.notna(dados),
        None
    )

    return dados.to_dict(orient="records")


def salvar_dados_mysql(
    df: Optional[pd.DataFrame]
) -> bool:
    """
    Insere ou atualiza os dados meteorológicos no MySQL.

    Returns:
        True se a gravação for concluída.
        False se ocorrer alguma falha.
    """

    if df is None or not isinstance(df, pd.DataFrame):
        logger.warning(
            "Não foi possível gravar: dados recebidos inválidos."
        )
        return False

    if df.empty:
        logger.warning(
            "Não foi possível gravar: DataFrame vazio."
        )
        return False

    engine = None

    try:
        logger.info(
            "Preparando %d registros para armazenamento.",
            len(df)
        )

        registros = preparar_registros(df)

        engine = criar_conexao()

        comando_sql = text("""
            INSERT INTO clima_diario (
                cidade,
                estado,
                data_referencia,
                temperatura_max_c,
                temperatura_min_c,
                precipitacao_mm,
                umidade_media_pct,
                vento_max_kmh,
                codigo_clima
            )
            VALUES (
                :cidade,
                :estado,
                :data_referencia,
                :temperatura_max_c,
                :temperatura_min_c,
                :precipitacao_mm,
                :umidade_media_pct,
                :vento_max_kmh,
                :codigo_clima
            )
            ON DUPLICATE KEY UPDATE
                temperatura_max_c = VALUES(temperatura_max_c),
                temperatura_min_c = VALUES(temperatura_min_c),
                precipitacao_mm = VALUES(precipitacao_mm),
                umidade_media_pct = VALUES(umidade_media_pct),
                vento_max_kmh = VALUES(vento_max_kmh),
                codigo_clima = VALUES(codigo_clima),
                data_coleta = CURRENT_TIMESTAMP
        """)

        # A transação garante que a operação seja concluída
        # integralmente ou revertida em caso de erro.
        with engine.begin() as conexao:
            conexao.execute(
                comando_sql,
                registros
            )

        logger.info(
            "Gravação concluída com sucesso: %d registros processados.",
            len(registros)
        )

        return True

    except ValueError:
        logger.exception(
            "Erro na validação das configurações ou dos dados."
        )

    except SQLAlchemyError:
        logger.exception(
            "Falha durante a operação no banco de dados MySQL."
        )

    finally:
        if engine is not None:
            engine.dispose()
            logger.info("Conexão com o MySQL encerrada.")

    return False
