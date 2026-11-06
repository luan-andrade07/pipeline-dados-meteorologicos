
from pathlib import Path
from dotenv import load_dotenv

from src.extract import buscar_dados_climaticos
from src.transform import validar_tratar_dados
from src.load import salvar_dados_mysql
from src.logging_config import logger


# Carrega as configurações da raiz do projeto
ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")


def executar_pipeline():
    """Coordena a execução completa do pipeline ETL."""

    logger.info("========== INÍCIO DO PIPELINE ==========")

    # 1. Extract
    dados = buscar_dados_climaticos()

    if dados is None:
        logger.error(
            "Pipeline interrompido durante a extração."
        )
        return False

    # 2. Transform
    dados_validos = validar_tratar_dados(dados)

    if dados_validos is None:
        logger.error(
            "Pipeline interrompido durante a transformação."
        )
        return False

    # 3. Load
    sucesso = salvar_dados_mysql(dados_validos)

    if sucesso:
        logger.info("PIPELINE FINALIZADO COM SUCESSO.")
        return True

    logger.error("PIPELINE FINALIZADO COM FALHAS.")
    return False


if __name__ == "__main__":
    executar_pipeline()
