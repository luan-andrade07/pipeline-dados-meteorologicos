
import sys
from pathlib import Path

from dotenv import load_dotenv


# Localiza a raiz do projeto e carrega as variáveis de ambiente
ROOT_DIR = Path(__file__).resolve().parent

load_dotenv(ROOT_DIR / ".env")


# Importações dos módulos do projeto
from src.extract import buscar_dados_climaticos
from src.transform import validar_tratar_dados
from src.load import salvar_dados_mysql
from src.logging_config import logger


def executar_pipeline() -> bool:
    """
    Coordena as etapas de extração, transformação e carregamento.

    Returns:
        True quando todas as etapas forem concluídas.
        False quando ocorrer alguma falha.
    """

    logger.info("========== INÍCIO DO PIPELINE ==========")

    try:
        # 1. EXTRAÇÃO
        logger.info("ETAPA 1/3: EXTRAÇÃO")

        dados = buscar_dados_climaticos()

        if dados is None:
            logger.error(
                "Pipeline interrompido: falha na extração."
            )
            return False

        logger.info("Extração finalizada com sucesso.")

        # 2. TRANSFORMAÇÃO
        logger.info("ETAPA 2/3: TRANSFORMAÇÃO")

        dados_validos = validar_tratar_dados(dados)

        if dados_validos is None:
            logger.error(
                "Pipeline interrompido: falha na transformação."
            )
            return False

        if dados_validos.empty:
            logger.error(
                "Pipeline interrompido: nenhum dado válido."
            )
            return False

        logger.info(
            "Transformação finalizada: %d registros válidos.",
            len(dados_validos)
        )

        # 3. CARREGAMENTO
        logger.info("ETAPA 3/3: CARREGAMENTO")

        sucesso = salvar_dados_mysql(dados_validos)

        if not sucesso:
            logger.error(
                "Pipeline interrompido: falha no carregamento."
            )
            return False

        logger.info(
            "========== PIPELINE FINALIZADO COM SUCESSO =========="
        )

        return True

    except Exception:
        logger.exception(
            "Erro inesperado durante a execução do pipeline."
        )
        return False


if __name__ == "__main__":

    sucesso = executar_pipeline()

    # Código 0 = sucesso
    # Código 1 = falha
    sys.exit(0 if sucesso else 1)
