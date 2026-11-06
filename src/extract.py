
import requests
import pandas as pd

from src.logging_config import logger


def buscar_dados_climaticos():
    """Busca dados meteorológicos na API Open-Meteo."""

    url = "https://api.open-meteo.com/v1/forecast"

    parametros = {
        "latitude": -23.5505,
        "longitude": -46.6333,
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "relative_humidity_2m_mean",
            "wind_speed_10m_max",
            "weather_code"
        ],
        "timezone": "America/Sao_Paulo",
        "forecast_days": 7
    }

    try:
        logger.info("Iniciando coleta na API Open-Meteo.")

        resposta = requests.get(
            url,
            params=parametros,
            timeout=30
        )

        resposta.raise_for_status()

        dados = resposta.json()
        diario = dados["daily"]

        df = pd.DataFrame({
            "data_referencia": diario["time"],
            "temperatura_max_c": diario["temperature_2m_max"],
            "temperatura_min_c": diario["temperature_2m_min"],
            "precipitacao_mm": diario["precipitation_sum"],
            "umidade_media_pct": diario["relative_humidity_2m_mean"],
            "vento_max_kmh": diario["wind_speed_10m_max"],
            "codigo_clima": diario["weather_code"]
        })

        df["cidade"] = "São Paulo"
        df["estado"] = "SP"

        logger.info(
            "Coleta concluída: %d registros recebidos.",
            len(df)
        )

        print("\nDADOS METEOROLÓGICOS:")
        print(df.to_string(index=False))

        return df

    except requests.exceptions.RequestException:
        logger.exception("Erro na comunicação com a API.")

    except (KeyError, ValueError):
        logger.exception("Erro ao processar a resposta da API.")

    return None
