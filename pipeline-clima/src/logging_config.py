
import logging

from pathlib import Path
from logging.handlers import RotatingFileHandler


# Localização da raiz do projeto
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Pasta onde os logs serão armazenados
PASTA_LOGS = PROJECT_ROOT / "logs"
PASTA_LOGS.mkdir(exist_ok=True)


def configurar_logger():
    """Configura os registros de execução do pipeline."""

    logger = logging.getLogger("pipeline_clima")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    formato = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    # Exibição no terminal
    console = logging.StreamHandler()
    console.setFormatter(formato)

    # Gravação em arquivo com rotação automática
    arquivo = RotatingFileHandler(
        PASTA_LOGS / "pipeline.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8"
    )

    arquivo.setFormatter(formato)

    logger.addHandler(console)
    logger.addHandler(arquivo)

    return logger


logger = configurar_logger()
