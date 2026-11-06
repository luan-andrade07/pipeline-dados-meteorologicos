
from typing import Any, Dict, Optional

import pandas as pd
import requests

from src.logging_config import logger


# Configurações da API
API_URL = "https://api.open-meteo.com/v1/forecast"

LATITUDE = -23.5505
LONGITUDE = -46.6333

CIDADE = "São Paulo"
ESTADO = "SP"

FUSO_HORARIO = "America/Sao_Paulo"
DIAS_PREVISAO = 7
TIMEOUT = 30


# Mapeamento entre as colunas do projeto e os campos da API
# O campo "time" é retornado automaticamente pela API.
MAPEAMENTO_COLUNAS = {
    "temperatura_max_c": "temperature_2m_max",
    "temperatura_min_c": "temperature_2m_min",
    "precipitacao_mm": "precipitation_sum",
    "umidade_media_pct": "relative_humidity_2m_mean",
    "vento_max_kmh": "wind_speed_10m_max",
    "codigo_clima": "weather_code"
}


def validar_resposta_api(
    dados: Any
) -> Dict[str, Any]:
    """Verifica se a resposta da API possui os dados esperados."""

    if not isinstance(dados, dict):
        raise ValueError(
            "A resposta da API não possui formato válido."
        )

    diario = dados.get("daily")

    if not isinstance(diario, dict):
        raise ValueError(
            "A resposta não contém a seção daily."
        )

    campos_obrigatorios = [
        "time",
        *MAPEAMENTO_COLUNAS.values()
    ]

    campos_ausentes = [
        campo
        for campo in campos_obrigatorios
        if campo not in diario
    ]

    if campos_ausentes:
        raise ValueError(
            f"Campos ausentes na resposta da API: {campos_ausentes}"
        )

    for campo in campos_obrigatorios:

        if not isinstance(diario[campo], list):
            raise ValueError(
                f"O campo {campo} não contém uma lista válida."
            )

    tamanhos = {
        len(diario[campo])
        for campo in campos_obrigatorios
    }

    if len(tamanhos) != 1:
        raise ValueError(
            "Os campos da API possuem quantidades diferentes de dados."
        )

    if not tamanhos or next(iter(tamanhos)) == 0:
        raise ValueError(
            "A API não retornou registros meteorológicos."
        )

    return diario


def buscar_dados_climaticos() -> Optional[pd.DataFrame]:
    """Coleta dados meteorológicos da API Open-Meteo."""

    parametros = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "daily": list(MAPEAMENTO_COLUNAS.values()),
        "timezone": FUSO_HORARIO,
        "forecast_days": DIAS_PREVISAO
    }

    try:
        logger.info(
            "Iniciando coleta na API Open-Meteo."
        )

        resposta = requests.get(
            API_URL,
            params=parametros,
            timeout=TIMEOUT
        )

        resposta.raise_for_status()

        dados = resposta.json()

        diario = validar_resposta_api(dados)

        # Organiza a data e as variáveis meteorológicas
        dados_organizados = {
            "data_referencia": diario["time"]
        }

        for nome_coluna, campo_api in MAPEAMENTO_COLUNAS.items():
            dados_organizados[nome_coluna] = diario[campo_api]

        df = pd.DataFrame(dados_organizados)

        # Adiciona informações de localização
        df["cidade"] = CIDADE
        df["estado"] = ESTADO

        logger.info(
            "Coleta concluída: %d registros recebidos para %s.",
            len(df),
            CIDADE
        )

        return df

    except requests.exceptions.Timeout:
        logger.exception(
            "Tempo limite excedido durante a consulta à API."
        )

    except requests.exceptions.HTTPError as erro:
        if erro.response is not None:
            logger.error(
                "Erro HTTP %s na API Open-Meteo: %s",
                erro.response.status_code,
                erro.response.text
            )
        else:
            logger.exception(
                "Erro HTTP durante a consulta à API."
            )

    except requests.exceptions.RequestException:
        logger.exception(
            "Falha na comunicação com a API Open-Meteo."
        )

    except (ValueError, TypeError, KeyError):
        logger.exception(
            "Erro ao validar ou processar os dados meteorológicos."
        )

    return None
