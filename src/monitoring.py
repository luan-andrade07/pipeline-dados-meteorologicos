
"""Registro de execuções do pipeline no MySQL (horários em UTC)."""

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.load import criar_conexao
from src.logging_config import logger

# =====================================================
# ESTRUTURA DAS TABELAS DE MONITORAMENTO
# =====================================================

CRIAR_EXECUCOES = text("""
    CREATE TABLE IF NOT EXISTS pipeline_execucoes (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        inicio_utc DATETIME(6) NOT NULL,
        fim_utc DATETIME(6) NULL,
        duracao_seg DECIMAL(12,3) NULL,
        status VARCHAR(20) NOT NULL,
        cidades_total INT NOT NULL DEFAULT 0,
        cidades_sucesso INT NOT NULL DEFAULT 0,
        cidades_falha INT NOT NULL DEFAULT 0,
        registros_processados INT NOT NULL DEFAULT 0,
        INDEX idx_pipeline_inicio (inicio_utc)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")

CRIAR_CIDADES = text("""
    CREATE TABLE IF NOT EXISTS pipeline_execucao_cidades (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        execucao_id BIGINT NOT NULL,
        cidade VARCHAR(100) NOT NULL,
        estado CHAR(2) NOT NULL,
        status VARCHAR(20) NOT NULL,
        etapa_falha VARCHAR(32) NULL,
        mensagem VARCHAR(255) NULL,
        registros_processados INT NOT NULL DEFAULT 0,
        duracao_seg DECIMAL(12,3) NOT NULL DEFAULT 0,
        INDEX idx_execucao_cidade (execucao_id),
        CONSTRAINT fk_pipeline_execucao
            FOREIGN KEY (execucao_id)
            REFERENCES pipeline_execucoes(id)
            ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")

# =====================================================
# COMANDOS SQL
# =====================================================

INSERIR_EXECUCAO = text("""
    INSERT INTO pipeline_execucoes (
        inicio_utc,
        status,
        cidades_total
    )
    VALUES (
        :inicio_utc,
        'EM_EXECUCAO',
        :cidades_total
    )
""")

INSERIR_CIDADE = text("""
    INSERT INTO pipeline_execucao_cidades (
        execucao_id,
        cidade,
        estado,
        status,
        etapa_falha,
        mensagem,
        registros_processados,
        duracao_seg
    )
    VALUES (
        :execucao_id,
        :cidade,
        :estado,
        :status,
        :etapa_falha,
        :mensagem,
        :registros_processados,
        :duracao_seg
    )
""")

ATUALIZAR_EXECUCAO = text("""
    UPDATE pipeline_execucoes
    SET
        fim_utc = :fim_utc,
        duracao_seg = :duracao_seg,
        status = :status,
        cidades_sucesso = :cidades_sucesso,
        cidades_falha = :cidades_falha,
        registros_processados = :registros_processados
    WHERE id = :execucao_id
""")

# =====================================================
# CONTROLE DE HORÁRIO
# =====================================================

def agora_utc():
    """Retorna o horário UTC para armazenamento no MySQL."""

    return datetime.now(
        timezone.utc
    ).replace(tzinfo=None)

# =====================================================
# INÍCIO DO MONITORAMENTO
# =====================================================

def iniciar_monitoramento(
    total_cidades: int,
    inicio_utc: datetime
):
    """
    Registra o início de uma execução.

    Retorna o ID gerado pelo MySQL ou None
    quando houver uma falha no monitoramento.
    """

    engine = None

    try:
        engine = criar_conexao()

        # A criação de tabelas fica separada
        # da transação de inserção.
        with engine.begin() as conexao:

            conexao.execute(CRIAR_EXECUCOES)
            conexao.execute(CRIAR_CIDADES)

        with engine.begin() as conexao:

            resultado = conexao.execute(
                INSERIR_EXECUCAO,
                {
                    "inicio_utc": inicio_utc,
                    "cidades_total": total_cidades
                }
            )

            execucao_id = int(
                resultado.lastrowid
            )

        logger.info(
            "Monitoramento iniciado: execução %d.",
            execucao_id
        )

        return execucao_id

    except (
        SQLAlchemyError,
        ValueError,
        TypeError,
        OSError
    ):

        logger.exception(
            "Não foi possível iniciar o monitoramento no MySQL."
        )

        return None

    finally:

        if engine is not None:
            engine.dispose()

# =====================================================
# FINALIZAÇÃO DO MONITORAMENTO
# =====================================================

def finalizar_monitoramento(
    execucao_id: int | None,
    status: str,
    duracao_seg: float,
    cidades_sucesso: int,
    cidades_falha: int,
    registros_processados: int,
    resultados_cidades: list[dict]
) -> bool:
    """
    Grava os resultados por cidade e finaliza
    a execução na mesma transação.

    Se não houver registro inicial, o monitoramento
    não interfere nas etapas do pipeline.
    """

    if execucao_id is None:
        return False

    if status not in {
        "SUCESSO",
        "PARCIAL",
        "FALHA"
    }:
        raise ValueError(
            f"Status de execução inválido: {status}"
        )

    engine = None

    try:

        engine = criar_conexao()

        with engine.begin() as conexao:

            if resultados_cidades:

                conexao.execute(
                    INSERIR_CIDADE,
                    [
                        {
                            **resultado,
                            "execucao_id": execucao_id
                        }
                        for resultado in resultados_cidades
                    ]
                )

            atualizacao = conexao.execute(
                ATUALIZAR_EXECUCAO,
                {
                    "execucao_id": execucao_id,
                    "fim_utc": agora_utc(),
                    "duracao_seg": round(
                        duracao_seg,
                        3
                    ),
                    "status": status,
                    "cidades_sucesso": cidades_sucesso,
                    "cidades_falha": cidades_falha,
                    "registros_processados":
                        registros_processados
                }
            )

            if atualizacao.rowcount != 1:
                raise ValueError(
                    "Execução não encontrada para finalizar."
                )

        logger.info(
            "Monitoramento finalizado: execução %d (%s).",
            execucao_id,
            status
        )

        return True

    except (
        SQLAlchemyError,
        ValueError,
        TypeError,
        OSError
    ):

        logger.exception(
            "Não foi possível finalizar o monitoramento no MySQL."
        )

        return False

    finally:

        if engine is not None:
            engine.dispose()