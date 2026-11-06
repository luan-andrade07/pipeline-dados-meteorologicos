
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError


# =====================================================
# CONFIGURAÇÃO
# =====================================================

ROOT_DIR = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = Path(__file__).resolve().parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")

st.set_page_config(
    page_title="Clima SP | Analytics",
    page_icon="🌦️",
    layout="wide",
    initial_sidebar_state="expanded"
)

from src.load import criar_conexao

from dashboard.components import (
    render_current_forecast,
    render_sidebar,
    render_header,
    render_metrics,
    render_temperature_chart,
    render_weather_charts,
    render_data_table,
    render_footer
)


# =====================================================
# CARREGAMENTO DO CSS
# =====================================================

def carregar_estilo():
    """Carrega o arquivo CSS externo."""

    caminho_css = DASHBOARD_DIR / "style.css"

    try:
        css = caminho_css.read_text(encoding="utf-8")

        st.markdown(
            f"<style>\n{css}\n</style>",
            unsafe_allow_html=True
        )

    except OSError:
        st.error("Não foi possível carregar dashboard/style.css.")


# =====================================================
# CONEXÃO E CONSULTA AO MYSQL
# =====================================================

@st.cache_resource
def obter_engine():
    """Cria uma conexão reutilizável com o MySQL."""

    return criar_conexao()


@st.cache_data(ttl=60)
def carregar_dados():
    """Consulta os dados meteorológicos armazenados."""

    comando_sql = text("""
        SELECT
            cidade,
            estado,
            data_referencia,
            temperatura_max_c,
            temperatura_min_c,
            precipitacao_mm,
            umidade_media_pct,
            vento_max_kmh,
            codigo_clima,
            data_coleta
        FROM clima_diario
        ORDER BY data_referencia
    """)

    engine = obter_engine()

    with engine.connect() as conexao:
        df = pd.read_sql_query(comando_sql, conexao)

    if not df.empty:

        df["data_referencia"] = pd.to_datetime(
            df["data_referencia"],
            errors="coerce"
        )

        df["data_coleta"] = pd.to_datetime(
            df["data_coleta"],
            errors="coerce"
        )

        df = df.dropna(subset=["data_referencia"])

    return df


# =====================================================
# APLICAÇÃO DOS FILTROS
# =====================================================

def aplicar_filtros(
    df: pd.DataFrame,
    cidade: str,
    periodo
) -> pd.DataFrame:
    """Aplica os filtros de cidade e período."""

    resultado = df.copy()

    if cidade != "Todas":
        resultado = resultado[
            resultado["cidade"] == cidade
        ]

    if isinstance(periodo, (tuple, list)):

        if len(periodo) == 2:

            data_inicio, data_fim = periodo

            resultado = resultado[
                resultado["data_referencia"].dt.date.between(
                    data_inicio,
                    data_fim
                )
            ]

        elif len(periodo) == 1:

            resultado = resultado[
                resultado["data_referencia"].dt.date
                == periodo[0]
            ]

    return resultado


# =====================================================
# EXECUÇÃO PRINCIPAL
# =====================================================

def main():
    """Coordena a apresentação do dashboard."""

    carregar_estilo()

    try:

        with st.spinner("Consultando banco de dados..."):
            df = carregar_dados()

    except (SQLAlchemyError, ValueError):

        st.error(
            "Não foi possível acessar o banco de dados MySQL."
        )

        st.caption(
            "Verifique se o servidor está em execução "
            "e se as configurações do arquivo .env estão corretas."
        )

        st.stop()

    except Exception as erro:

        st.error("Ocorreu um erro inesperado ao carregar os dados.")
        st.exception(erro)
        st.stop()

    if df.empty:

        st.warning(
            "Nenhum registro encontrado. "
            "Execute o pipeline ETL antes de abrir o dashboard."
        )

        st.stop()

    # Menu e filtros
    cidade, periodo, atualizar = render_sidebar(df)

    if atualizar:
        carregar_dados.clear()
        st.rerun()

    # Aplicação dos filtros
    df_filtrado = aplicar_filtros(
        df,
        cidade,
        periodo
    )

    if df_filtrado.empty:

        st.warning(
            "Não existem registros para os filtros selecionados."
        )

        st.stop()

    cidade_atual = (
        "Todas as cidades"
        if cidade == "Todas"
        else cidade
    )

    # Apresentação dos componentes
    render_header(cidade_atual)
    render_current_forecast(df)
    render_metrics(df_filtrado)

    render_temperature_chart(df_filtrado)

    render_weather_charts(df_filtrado)

    render_data_table(df_filtrado)

    render_footer()


if __name__ == "__main__":
    main()