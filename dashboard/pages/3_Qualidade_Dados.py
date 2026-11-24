
"""Painel de qualidade das previsões meteorológicas."""

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

ROOT_DIR = Path(__file__).resolve().parents[2]
DASHBOARD_DIR = ROOT_DIR / "dashboard"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")

st.set_page_config(
    page_title="Qualidade dos Dados | Clima Brasil",
    page_icon="🛡️",
    layout="wide",
)

from src.extract import CIDADES, DIAS_PREVISAO
from src.load import criar_conexao
from src.quality import analisar_qualidade


# =====================================================
# CONSULTA DAS PREVISÕES
# =====================================================

@st.cache_data(ttl=60)
def carregar_previsoes():
    """Obtém previsões e horários de coleta em UTC."""

    consulta = text("""
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
            UNIX_TIMESTAMP(data_coleta) AS coleta_epoch
        FROM clima_diario
    """)

    engine = criar_conexao()

    try:

        with engine.connect() as conexao:

            dados = pd.read_sql_query(
                consulta,
                conexao
            )

    finally:
        engine.dispose()

    dados["coleta_utc"] = pd.to_datetime(
        pd.to_numeric(
            dados.pop("coleta_epoch"),
            errors="coerce"
        ),
        unit="s",
        utc=True,
        errors="coerce"
    )

    return dados


# =====================================================
# FORMATAÇÃO DAS DATAS
# =====================================================

def formatar_data(valor):

    if pd.isna(valor):
        return "Não disponível"

    return pd.Timestamp(valor).tz_convert(
        "America/Sao_Paulo"
    ).strftime("%d/%m/%Y %H:%M")


# =====================================================
# EXECUÇÃO DA PÁGINA
# =====================================================

def main():

    # Reutiliza o CSS do projeto.
    try:

        css = (
            DASHBOARD_DIR / "style.css"
        ).read_text(
            encoding="utf-8"
        )

        st.markdown(
            f"<style>\n{css}\n</style>",
            unsafe_allow_html=True
        )

    except OSError:
        pass

    st.title(
        "🛡️ Qualidade dos dados meteorológicos"
    )

    st.caption(
        "Auditoria das previsões armazenadas no MySQL. "
        "Valida os próximos sete dias, a consistência "
        "dos valores e a atualização das coletas."
    )

    # =============================================
    # ATUALIZAÇÃO
    # =============================================

    if st.button(
        "↻ Atualizar análise"
    ):

        carregar_previsoes.clear()
        st.rerun()

    # =============================================
    # ANÁLISE DA QUALIDADE
    # =============================================

    try:

        with st.spinner(
            "Verificando a qualidade das previsões..."
        ):

            dados = carregar_previsoes()

            resumo, ocorrencias = analisar_qualidade(
                dados,
                CIDADES,
                dias_previsao=DIAS_PREVISAO
            )

    except (
        SQLAlchemyError,
        ValueError,
        OSError
    ) as erro:

        st.error(
            "Não foi possível analisar os dados do MySQL."
        )

        st.caption(str(erro))
        st.stop()

    # =============================================
    # INDICADORES
    # =============================================

    ok = int(
        (resumo["Status"] == "OK").sum()
    )

    atencao = int(
        (resumo["Status"] == "ATENÇÃO").sum()
    )

    critico = int(
        (resumo["Status"] == "CRÍTICO").sum()
    )

    faltantes = int(
        resumo["Datas ausentes"].sum()
    )

    a, b, c, d = st.columns(4)

    a.metric(
        "✅ Cidades em dia",
        ok
    )

    b.metric(
        "🟡 Atenção",
        atencao
    )

    c.metric(
        "🔴 Crítico",
        critico
    )

    d.metric(
        "📅 Datas ausentes",
        faltantes
    )

    # =============================================
    # STATUS GERAL
    # =============================================

    if critico:

        st.error(
            "Há problemas críticos de qualidade: "
            "confira as cidades com dados ausentes, "
            "inválidos ou muito antigos."
        )

    elif atencao:

        st.warning(
            "Há cidades que precisam de atenção "
            "quanto à atualização."
        )

    else:

        st.success(
            "Todas as cidades passaram nas "
            "verificações configuradas."
        )

    # =============================================
    # TABELA POR CIDADE
    # =============================================

    st.subheader(
        "Situação por cidade"
    )

    tabela = resumo.copy()

    tabela["Última coleta (Brasília)"] = (
        tabela["Última coleta UTC"].apply(
            formatar_data
        )
    )

    tabela = tabela.drop(
        columns=["Última coleta UTC"]
    )

    tabela["Atraso (h)"] = (
        tabela["Atraso (h)"].round(1)
    )

    st.dataframe(
        tabela,
        hide_index=True,
        width="stretch"
    )

    # =============================================
    # OCORRÊNCIAS DETECTADAS
    # =============================================

    st.subheader(
        "Ocorrências encontradas"
    )

    if ocorrencias.empty:

        st.info(
            "Nenhuma ocorrência identificada "
            "na janela analisada."
        )

    else:

        st.dataframe(
            ocorrencias,
            hide_index=True,
            width="stretch"
        )

    # =============================================
    # DOCUMENTAÇÃO DOS CRITÉRIOS
    # =============================================

    with st.expander(
        "Como a qualidade é avaliada?"
    ):

        st.write(
            f"**Cobertura:** uma previsão por cidade "
            f"para cada um dos {DIAS_PREVISAO} dias, "
            "começando hoje (horário de Brasília)."
        )

        st.write(
            "**Consistência:** temperaturas entre "
            "-90 e 60 °C, mínima não superior "
            "à máxima, precipitação e vento não "
            "negativos, umidade entre 0 e 100%, "
            "código de clima inteiro não negativo "
            "e ausência de medições nulas."
        )

        st.write(
            "**Atualização:** atenção após 36 horas "
            "sem coleta e nível crítico após "
            "72 horas. São parâmetros internos "
            "do projeto."
        )

        st.caption(
            "Esta é uma análise de integridade "
            "dos dados armazenados, não uma "
            "validação da precisão das previsões "
            "da Open-Meteo. Não modifica nenhuma tabela."
        )


if __name__ == "__main__":
    main()
