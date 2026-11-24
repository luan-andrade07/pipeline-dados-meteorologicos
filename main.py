
"""Coordena a coleta, validação e persistência de múltiplas cidades."""

import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# =====================================================
# CONFIGURAÇÃO INICIAL
# =====================================================

ROOT_DIR = Path(__file__).resolve().parent

load_dotenv(ROOT_DIR / ".env")

# =====================================================
# IMPORTAÇÕES DO PIPELINE
# =====================================================

from src.extract import (
    CIDADES,
    buscar_dados_climaticos
)

from src.transform import validar_tratar_dados
from src.load import salvar_dados_mysql
from src.logging_config import logger

from src.monitoring import (
    agora_utc,
    iniciar_monitoramento,
    finalizar_monitoramento
)

# =====================================================
# EXECUÇÃO DO PIPELINE
# =====================================================

def executar_pipeline() -> bool:
    """
    Executa o ETL para todas as cidades.

    Registra o desempenho de cada cidade e
    o resultado geral do processamento.
    """

    inicio = time.perf_counter()
    inicio_utc = agora_utc()

    total_cidades = len(CIDADES)
    cidades_sucesso = 0
    registros_processados = 0

    resultados_cidades = []

    logger.info(
        "========== INÍCIO DO PIPELINE =========="
    )

    logger.info(
        "Total de cidades configuradas: %d",
        total_cidades
    )

    # Uma falha no registro do monitoramento
    # não deve impedir a execução do ETL.
    execucao_id = iniciar_monitoramento(
        total_cidades,
        inicio_utc
    )

    # =================================================
    # PROCESSAMENTO DAS CIDADES
    # =================================================

    for numero, localidade in enumerate(
        CIDADES,
        start=1
    ):

        cidade = localidade["cidade"]
        estado = localidade["estado"]

        identificacao = f"{cidade}/{estado}"

        inicio_cidade = time.perf_counter()

        etapa = "EXTRACAO"
        status_cidade = "FALHA"
        mensagem = None
        quantidade = 0

        logger.info(
            "========== CIDADE %d/%d: %s ==========",
            numero,
            total_cidades,
            identificacao
        )

        try:

            # =========================================
            # ETAPA 1 - EXTRAÇÃO
            # =========================================

            logger.info("ETAPA 1/3: EXTRAÇÃO")

            dados = buscar_dados_climaticos(
                localidade
            )

            if dados is None or dados.empty:

                mensagem = (
                    "Nenhum dado recebido da API."
                )

                logger.error(
                    "Falha na extração de %s.",
                    identificacao
                )

                continue

            logger.info(
                "Extração concluída: %d registros.",
                len(dados)
            )

            # =========================================
            # ETAPA 2 - TRANSFORMAÇÃO
            # =========================================

            etapa = "TRANSFORMACAO"

            logger.info(
                "ETAPA 2/3: TRANSFORMAÇÃO"
            )

            dados_validos = validar_tratar_dados(
                dados
            )

            if (
                dados_validos is None
                or dados_validos.empty
            ):

                mensagem = (
                    "Nenhum registro válido após transformação."
                )

                logger.error(
                    "Falha na transformação de %s.",
                    identificacao
                )

                continue

            logger.info(
                "Transformação concluída: %d registros válidos.",
                len(dados_validos)
            )

            # =========================================
            # ETAPA 3 - CARREGAMENTO
            # =========================================

            etapa = "CARREGAMENTO"

            logger.info(
                "ETAPA 3/3: CARREGAMENTO"
            )

            if not salvar_dados_mysql(
                dados_validos
            ):

                mensagem = (
                    "Falha ao gravar dados no MySQL."
                )

                logger.error(
                    "Falha no carregamento de %s.",
                    identificacao
                )

                continue

            # =========================================
            # CIDADE PROCESSADA COM SUCESSO
            # =========================================

            quantidade = len(dados_validos)

            registros_processados += quantidade
            cidades_sucesso += 1

            status_cidade = "SUCESSO"
            etapa = None

            logger.info(
                "Cidade processada com sucesso: %s.",
                identificacao
            )

        except Exception:

            mensagem = (
                "Erro inesperado; consulte logs/pipeline.log."
            )

            logger.exception(
                "Erro inesperado ao processar %s.",
                identificacao
            )

        finally:

            # Registra o resultado independentemente
            # de sucesso ou falha.
            resultados_cidades.append({
                "cidade": cidade,
                "estado": estado,
                "status": status_cidade,
                "etapa_falha": (
                    etapa
                    if status_cidade == "FALHA"
                    else None
                ),
                "mensagem": mensagem,
                "registros_processados": quantidade,
                "duracao_seg": round(
                    time.perf_counter()
                    - inicio_cidade,
                    3
                )
            })

    # =================================================
    # RESUMO DA EXECUÇÃO
    # =================================================

    cidades_falha = (
        total_cidades - cidades_sucesso
    )

    duracao_seg = (
        time.perf_counter() - inicio
    )

    if cidades_falha == 0:
        status = "SUCESSO"

    elif cidades_sucesso > 0:
        status = "PARCIAL"

    else:
        status = "FALHA"

    logger.info(
        "========== RESUMO DO PIPELINE =========="
    )

    logger.info(
        "Cidades configuradas: %d",
        total_cidades
    )

    logger.info(
        "Cidades processadas: %d",
        cidades_sucesso
    )

    logger.info(
        "Registros gravados ou atualizados: %d",
        registros_processados
    )

    logger.info(
        "Cidades com falha: %d",
        cidades_falha
    )

    logger.info(
        "Duração total: %.2f segundos",
        duracao_seg
    )

    # =================================================
    # ARMAZENAMENTO DO MONITORAMENTO
    # =================================================

    finalizar_monitoramento(
        execucao_id=execucao_id,
        status=status,
        duracao_seg=duracao_seg,
        cidades_sucesso=cidades_sucesso,
        cidades_falha=cidades_falha,
        registros_processados=registros_processados,
        resultados_cidades=resultados_cidades
    )

    # =================================================
    # RESULTADO FINAL
    # =================================================

    if status == "SUCESSO":

        logger.info(
            "========== PIPELINE FINALIZADO COM SUCESSO =========="
        )

    else:

        logger.error(
            "========== PIPELINE FINALIZADO COM FALHAS (%s) ==========",
            status
        )

        falhas = [
            f"{resultado['cidade']}/{resultado['estado']}"
            for resultado in resultados_cidades
            if resultado["status"] == "FALHA"
        ]

        logger.error(
            "Cidades com falha: %s",
            ", ".join(falhas)
        )

    return status == "SUCESSO"

# =====================================================
# INICIALIZAÇÃO
# =====================================================

if __name__ == "__main__":

    sys.exit(
        0 if executar_pipeline() else 1
    )