
import os
from datetime import datetime, timezone
from typing import Dict, Optional

import pandas as pd

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine
from sqlalchemy.exc import SQLAlchemyError

from src.logging_config import logger


# =====================================================
# CONFIGURAÇÕES DO BANCO
# =====================================================

VARIAVEIS_AMBIENTE = [
    "MYSQL_HOST",
    "MYSQL_PORT",
    "MYSQL_DATABASE",
    "MYSQL_USER",
    "MYSQL_PASSWORD"
]

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


# =====================================================
# CONFIGURAÇÕES DE CONEXÃO
# =====================================================

def obter_configuracoes_banco() -> Dict[str, str]:
    """Obtém e valida as configurações do MySQL."""

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
            "MYSQL_PORT precisa ser um número inteiro."
        ) from erro

    if not 1 <= porta <= 65535:
        raise ValueError(
            "A porta do MySQL precisa estar entre 1 e 65535."
        )

    configuracoes["MYSQL_PORT"] = str(porta)

    return configuracoes


def criar_conexao() -> Engine:
    """Cria uma conexão com o banco MySQL."""

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


# =====================================================
# PREPARAÇÃO DOS REGISTROS
# =====================================================

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

    dados["data_referencia"] = pd.to_datetime(
        dados["data_referencia"],
        errors="raise"
    ).dt.date

    # Converte valores ausentes para None.
    dados = dados.astype(object).where(
        pd.notna(dados),
        None
    )

    return dados.to_dict(orient="records")


# =====================================================
# CRIAÇÃO DA TABELA HISTÓRICA
# =====================================================

def garantir_tabela_historico(conexao):
    """
    Cria a tabela histórica caso não exista.

    Não exclui nem modifica os registros
    da tabela principal.
    """

    comando_sql = text("""
        CREATE TABLE IF NOT EXISTS clima_diario_historico (

            id BIGINT AUTO_INCREMENT PRIMARY KEY,

            cidade VARCHAR(100) NOT NULL,
            estado CHAR(2) NOT NULL,
            data_referencia DATE NOT NULL,

            temperatura_max_c DECIMAL(5,2),
            temperatura_min_c DECIMAL(5,2),

            precipitacao_mm DECIMAL(7,2),
            umidade_media_pct DECIMAL(5,2),
            vento_max_kmh DECIMAL(7,2),

            codigo_clima INT,

            data_coleta_utc DATETIME(6) NOT NULL,

            INDEX idx_historico_cidade_data (
                cidade,
                estado,
                data_referencia,
                data_coleta_utc
            )

        ) ENGINE=InnoDB
          DEFAULT CHARSET=utf8mb4
          COLLATE=utf8mb4_unicode_ci
    """)

    conexao.execute(comando_sql)


# =====================================================
# COMANDO DE ATUALIZAÇÃO DA TABELA PRINCIPAL
# =====================================================

COMANDO_PREVISAO_ATUAL = text("""
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


# =====================================================
# COMANDO DE INSERÇÃO DO HISTÓRICO
# =====================================================

COMANDO_HISTORICO = text("""
    INSERT INTO clima_diario_historico (
        cidade,
        estado,
        data_referencia,
        temperatura_max_c,
        temperatura_min_c,
        precipitacao_mm,
        umidade_media_pct,
        vento_max_kmh,
        codigo_clima,
        data_coleta_utc
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
        :codigo_clima,
        :data_coleta_utc
    )
""")


# =====================================================
# CARREGAMENTO DAS PREVISÕES
# =====================================================

def salvar_dados_mysql(
    df: Optional[pd.DataFrame]
) -> bool:
    """
    Salva os dados em duas tabelas.

    clima_diario:
        Mantém a previsão mais recente de
        cada cidade e data.

    clima_diario_historico:
        Preserva uma cópia de cada nova coleta.

    As duas gravações ocorrem em uma transação
    para evitar registros inconsistentes.
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

        # Registra a coleta em UTC.
        # DATETIME do MySQL não guarda fuso horário;
        # o sufixo _utc documenta a convenção usada.
        momento_coleta = datetime.now(
            timezone.utc
        ).replace(tzinfo=None)

        registros_historicos = [
            {
                **registro,
                "data_coleta_utc": momento_coleta
            }
            for registro in registros
        ]

        engine = criar_conexao()

        # Prepara a estrutura antes de iniciar
        # a transação de gravação dos dados.
        with engine.begin() as conexao:

            garantir_tabela_historico(
                conexao
            )

        # As duas inserções fazem parte
        # da mesma transação.
        with engine.begin() as conexao:

            # Atualiza a previsão mais recente.
            conexao.execute(
                COMANDO_PREVISAO_ATUAL,
                registros
            )

            # Registra uma nova versão histórica.
            conexao.execute(
                COMANDO_HISTORICO,
                registros_historicos
            )

        logger.info(
            "Gravação concluída com sucesso: %d registros processados.",
            len(registros)
        )

        logger.info(
            "Histórico atualizado: %d novos registros.",
            len(registros_historicos)
        )

        logger.info(
            "Horário da coleta (UTC): %s",
            momento_coleta.isoformat()
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

            logger.info(
                "Conexão com o MySQL encerrada."
            )

    return False
