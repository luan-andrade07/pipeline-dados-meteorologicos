
import os

import pandas as pd

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError

from src.logging_config import logger


def criar_conexao():
    """Cria a conexão com o banco de dados MySQL."""

    configuracoes = {
        "MYSQL_HOST": os.getenv("MYSQL_HOST"),
        "MYSQL_PORT": os.getenv("MYSQL_PORT"),
        "MYSQL_DATABASE": os.getenv("MYSQL_DATABASE"),
        "MYSQL_USER": os.getenv("MYSQL_USER"),
        "MYSQL_PASSWORD": os.getenv("MYSQL_PASSWORD")
    }

    faltando = [
        chave
        for chave, valor in configuracoes.items()
        if valor is None or valor == ""
    ]

    if faltando:
        raise ValueError(
            f"Configurações ausentes no .env: {faltando}"
        )

    url = URL.create(
        drivername="mysql+pymysql",
        username=configuracoes["MYSQL_USER"],
        password=configuracoes["MYSQL_PASSWORD"],
        host=configuracoes["MYSQL_HOST"],
        port=int(configuracoes["MYSQL_PORT"]),
        database=configuracoes["MYSQL_DATABASE"]
    )

    return create_engine(
        url,
        pool_pre_ping=True
    )


def salvar_dados_mysql(df):
    """Insere ou atualiza os dados meteorológicos no MySQL."""

    engine = None

    try:
        logger.info("Iniciando gravação no banco MySQL.")

        engine = criar_conexao()

        colunas = [
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

        dados = df[colunas].copy()

        dados["data_referencia"] = pd.to_datetime(
            dados["data_referencia"]
        ).dt.date

        # Converte valores ausentes em None
        dados = dados.astype(object).where(
            pd.notna(dados),
            None
        )

        registros = dados.to_dict(orient="records")

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

        with engine.begin() as conexao:
            conexao.execute(
                comando_sql,
                registros
            )

        logger.info(
            "Gravação concluída: %d registros processados.",
            len(registros)
        )

        return True

    except ValueError:
        logger.exception(
            "Erro nas configurações do banco de dados."
        )

    except SQLAlchemyError:
        logger.exception(
            "Erro durante a gravação no MySQL."
        )

    finally:
        if engine is not None:
            engine.dispose()

    return False
