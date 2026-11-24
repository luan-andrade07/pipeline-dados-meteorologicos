
from typing import Any, Dict, Optional

import pandas as pd
import requests

from src.logging_config import logger


# =====================================================
# CONFIGURAÇÕES DA API
# =====================================================

API_URL = "https://api.open-meteo.com/v1/forecast"
DIAS_PREVISAO = 7
TIMEOUT = 30


# =====================================================
# CIDADES MONITORADAS
# =====================================================

CIDADES = [
    {
        "cidade": "São Paulo",
        "estado": "SP",
        "latitude": -23.5505,
        "longitude": -46.6333,
        "timezone": "America/Sao_Paulo"
    },
    {
        "cidade": "Rio de Janeiro",
        "estado": "RJ",
        "latitude": -22.9068,
        "longitude": -43.1729,
        "timezone": "America/Sao_Paulo"
    },
    {
        "cidade": "Belo Horizonte",
        "estado": "MG",
        "latitude": -19.9167,
        "longitude": -43.9345,
        "timezone": "America/Sao_Paulo"
    },
    {
        "cidade": "Brasília",
        "estado": "DF",
        "latitude": -15.7939,
        "longitude": -47.8828,
        "timezone": "America/Sao_Paulo"
    },
    {
        "cidade": "Curitiba",
        "estado": "PR",
        "latitude": -25.4284,
        "longitude": -49.2733,
        "timezone": "America/Sao_Paulo"
    },
    {
        "cidade": "Recife",
        "estado": "PE",
        "latitude": -8.0476,
        "longitude": -34.8770,
        "timezone": "America/Recife"
    }
]


# =====================================================
# MAPEAMENTO DAS COLUNAS
# =====================================================

MAPEAMENTO_COLUNAS = {
    "temperatura_max_c": "temperature_2m_max",
    "temperatura_min_c": "temperature_2m_min",
    "precipitacao_mm": "precipitation_sum",
    "umidade_media_pct": "relative_humidity_2m_mean",
    "vento_max_kmh": "wind_speed_10m_max",
    "codigo_clima": "weather_code"
}


# =====================================================
# VALIDAÇÃO DA RESPOSTA DA API
# =====================================================

def validar_resposta_api(
    dados: Any
) -> Dict[str, Any]:
    """Verifica se a API retornou os campos esperados."""

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


# =====================================================
# EXTRAÇÃO DOS DADOS METEOROLÓGICOS
# =====================================================

def buscar_dados_climaticos(
    localidade: Optional[Dict[str, Any]] = None
) -> Optional[pd.DataFrame]:
    """
    Consulta as previsões meteorológicas de uma cidade.

    Quando nenhuma localidade for informada,
    utiliza São Paulo como padrão para manter
    compatibilidade com o funcionamento anterior.
    """

    if localidade is None:
        localidade = CIDADES[0]

    try:

        cidade = localidade["cidade"]
        estado = localidade["estado"]

        parametros = {
            "latitude": localidade["latitude"],
            "longitude": localidade["longitude"],
            "daily": list(MAPEAMENTO_COLUNAS.values()),
            "timezone": localidade["timezone"],
            "forecast_days": DIAS_PREVISAO
        }

        logger.info(
            "Iniciando coleta meteorológica: %s/%s.",
            cidade,
            estado
        )

        resposta = requests.get(
            API_URL,
            params=parametros,
            timeout=TIMEOUT
        )

        resposta.raise_for_status()

        dados = resposta.json()

        diario = validar_resposta_api(dados)

        dados_organizados = {
            "data_referencia": diario["time"]
        }

        for nome_coluna, campo_api in MAPEAMENTO_COLUNAS.items():
            dados_organizados[nome_coluna] = diario[campo_api]

        df = pd.DataFrame(dados_organizados)

        # Identifica a cidade de cada previsão
        df["cidade"] = cidade
        df["estado"] = estado

        logger.info(
            "Coleta concluída: %s/%s | %d registros.",
            cidade,
            estado,
            len(df)
        )

        return df

    except requests.exceptions.Timeout:
        logger.exception(
            "Tempo limite excedido durante a consulta à API."
        )

    except requests.exceptions.HTTPError as erro:

        if erro.response is not None:
            logger.error(
                "Erro HTTP %s na Open-Meteo: %s",
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
