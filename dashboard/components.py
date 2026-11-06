
import pandas as pd
import plotly.express as px
import streamlit as st


# =====================================================
# CONDIÇÕES METEOROLÓGICAS - CÓDIGOS WMO
# =====================================================

CONDICOES_CLIMATICAS = {
    0: ("☀️", "Céu limpo"),
    1: ("🌤️", "Predominantemente limpo"),
    2: ("⛅", "Parcialmente nublado"),
    3: ("☁️", "Nublado"),
    45: ("🌫️", "Nevoeiro"),
    48: ("🌫️", "Nevoeiro com geada"),
    51: ("🌦️", "Chuvisco fraco"),
    53: ("🌦️", "Chuvisco moderado"),
    55: ("🌧️", "Chuvisco intenso"),
    56: ("🌧️", "Chuvisco congelante fraco"),
    57: ("🌧️", "Chuvisco congelante intenso"),
    61: ("🌧️", "Chuva fraca"),
    63: ("🌧️", "Chuva moderada"),
    65: ("🌧️", "Chuva forte"),
    66: ("🌧️", "Chuva congelante fraca"),
    67: ("🌧️", "Chuva congelante forte"),
    71: ("❄️", "Neve fraca"),
    73: ("❄️", "Neve moderada"),
    75: ("❄️", "Neve forte"),
    77: ("❄️", "Grãos de neve"),
    80: ("🌦️", "Pancadas de chuva fracas"),
    81: ("🌧️", "Pancadas de chuva moderadas"),
    82: ("⛈️", "Pancadas de chuva fortes"),
    85: ("🌨️", "Pancadas de neve fracas"),
    86: ("🌨️", "Pancadas de neve fortes"),
    95: ("⛈️", "Trovoada"),
    96: ("⛈️", "Trovoada com granizo fraco"),
    99: ("⛈️", "Trovoada com granizo forte")
}


# =====================================================
# FUNÇÕES AUXILIARES
# =====================================================

def formatar_valor(
    valor,
    unidade: str,
    casas: int = 1
) -> str:
    """Formata valores numéricos."""

    if pd.isna(valor):
        return "N/D"

    return f"{valor:.{casas}f} {unidade}"


def descrever_condicao(codigo) -> tuple[str, str]:
    """Converte o código meteorológico em descrição."""

    if pd.isna(codigo):
        return "🌡️", "Condição não informada"

    try:
        codigo = int(codigo)
    except (ValueError, TypeError, OverflowError):
        return "🌡️", "Condição não informada"

    return CONDICOES_CLIMATICAS.get(
        codigo,
        ("🌡️", "Condição não identificada")
    )


def configurar_grafico(fig):
    """Aplica o padrão visual aos gráficos Plotly."""

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",

        font=dict(
            family="Segoe UI, Arial, sans-serif",
            color="#A9BAD0",
            size=11
        ),

        margin=dict(
            l=15,
            r=15,
            t=25,
            b=15
        ),

        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0
        ),

        hoverlabel=dict(
            bgcolor="#172338",
            bordercolor="#334155",
            font_color="#F8FAFC"
        )
    )

    fig.update_xaxes(
        showgrid=False,
        showline=True,
        linecolor="#26364D"
    )

    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(148,163,184,0.10)",
        zeroline=False
    )

    return fig


# =====================================================
# MENU LATERAL
# =====================================================

def render_sidebar(df: pd.DataFrame):
    """Exibe o menu e retorna os filtros selecionados."""

    with st.sidebar:

        st.title("🌦️ CLIMA SP")

        st.caption("WEATHER ANALYTICS")

        st.divider()

        st.subheader("Controle do painel")

        atualizar = st.button(
            "↻ Atualizar dados",
            use_container_width=True
        )

        st.divider()

        st.subheader("Filtros")

        cidades = sorted(
            df["cidade"].dropna().unique().tolist()
        )

        cidade_selecionada = st.selectbox(
            "Cidade",
            options=["Todas"] + cidades
        )

        data_minima = df["data_referencia"].min().date()
        data_maxima = df["data_referencia"].max().date()

        periodo = st.date_input(
            "Período da previsão",
            value=(data_minima, data_maxima),
            min_value=data_minima,
            max_value=data_maxima,
            format="DD/MM/YYYY"
        )

        st.divider()

        st.subheader("Sobre os dados")

        st.write("**Fonte:** Open-Meteo API")

        st.caption("Dados armazenados no MySQL.")

        st.caption("PIPELINE ETL")

        st.caption("PYTHON • PANDAS • MYSQL")

    return cidade_selecionada, periodo, atualizar


# =====================================================
# CABEÇALHO
# =====================================================

def render_header(cidade: str):
    """Exibe o cabeçalho principal."""

    with st.container(border=True):

        st.caption("DATA ANALYTICS • METEOROLOGIA")

        st.title("🌤️ Dashboard Meteorológico")

        st.write(
            f"Análise das previsões meteorológicas de {cidade}."
        )

        st.caption("🟢 Dados conectados ao MySQL")


# =====================================================
# DESTAQUE DA PRÓXIMA PREVISÃO
# =====================================================

def render_current_forecast(df: pd.DataFrame):
    """
    Exibe a previsão da data mais próxima a partir de hoje.

    Não representa uma medição meteorológica em tempo real.
    """

    hoje = pd.Timestamp.now(
        tz="America/Sao_Paulo"
    ).date()

    previsoes = df[
        df["data_referencia"].dt.date >= hoje
    ].copy()

    if previsoes.empty:
        st.info(
            "Não há previsões disponíveis a partir da data atual."
        )
        return

    previsoes = previsoes.sort_values(
        "data_referencia"
    )

    previsao = previsoes.iloc[0]

    icone, condicao = descrever_condicao(
        previsao["codigo_clima"]
    )

    data_previsao = (
        previsao["data_referencia"].strftime("%d/%m/%Y")
    )

    st.subheader("Destaque meteorológico")

    st.caption(
        f"Condição prevista para {data_previsao}."
    )

    with st.container(border=True):

        col_condicao, col_min, col_max, col_chuva, col_vento = (
            st.columns([2, 1, 1, 1, 1])
        )

        with col_condicao:
            st.markdown(f"## {icone} {condicao}")
            st.caption("Condição meteorológica prevista")

        with col_min:
            st.metric(
                "Temperatura mínima",
                formatar_valor(
                    previsao["temperatura_min_c"],
                    "°C"
                )
            )

        with col_max:
            st.metric(
                "Temperatura máxima",
                formatar_valor(
                    previsao["temperatura_max_c"],
                    "°C"
                )
            )

        with col_chuva:
            st.metric(
                "Precipitação",
                formatar_valor(
                    previsao["precipitacao_mm"],
                    "mm"
                )
            )

        with col_vento:
            st.metric(
                "Vento máximo",
                formatar_valor(
                    previsao["vento_max_kmh"],
                    "km/h"
                )
            )


# =====================================================
# INDICADORES
# =====================================================

def render_metrics(df: pd.DataFrame):
    """Exibe os indicadores meteorológicos."""

    temperatura_maxima = df["temperatura_max_c"].max()
    temperatura_minima = df["temperatura_min_c"].min()

    precipitacao_total = df["precipitacao_mm"].sum(
        min_count=1
    )

    umidade_media = df["umidade_media_pct"].mean()
    vento_maximo = df["vento_max_kmh"].max()

    st.subheader("Visão geral")

    st.caption(
        "Principais indicadores do período selecionado."
    )

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            "🌡️ Temperatura máxima",
            formatar_valor(temperatura_maxima, "°C")
        )

    with col2:
        st.metric(
            "❄️ Temperatura mínima",
            formatar_valor(temperatura_minima, "°C")
        )

    with col3:
        st.metric(
            "🌧️ Precipitação total",
            formatar_valor(precipitacao_total, "mm")
        )

    with col4:
        st.metric(
            "💧 Umidade média",
            formatar_valor(umidade_media, "%")
        )

    with col5:
        st.metric(
            "💨 Vento máximo",
            formatar_valor(vento_maximo, "km/h")
        )


# =====================================================
# GRÁFICO DE TEMPERATURA
# =====================================================

def render_temperature_chart(df: pd.DataFrame):
    """Compara temperaturas máximas e mínimas."""

    st.subheader("Análise de temperatura")

    st.caption(
        "Comparação entre temperaturas máximas e mínimas por dia."
    )

    with st.container(border=True):

        dados = df.melt(
            id_vars=["data_referencia"],
            value_vars=[
                "temperatura_max_c",
                "temperatura_min_c"
            ],
            var_name="medicao",
            value_name="temperatura"
        )

        dados["medicao"] = dados["medicao"].map({
            "temperatura_max_c": "Temperatura máxima",
            "temperatura_min_c": "Temperatura mínima"
        })

        fig = px.line(
            dados,
            x="data_referencia",
            y="temperatura",
            color="medicao",
            markers=True,

            color_discrete_map={
                "Temperatura máxima": "#F59E0B",
                "Temperatura mínima": "#38BDF8"
            },

            labels={
                "data_referencia": "Data",
                "temperatura": "Temperatura (°C)",
                "medicao": "Medição"
            }
        )

        fig.update_traces(
            line_width=3,
            marker_size=8
        )

        fig = configurar_grafico(fig)

        st.plotly_chart(
            fig,
            width="stretch",
            config={"displayModeBar": False}
        )


# =====================================================
# GRÁFICOS COMPLEMENTARES
# =====================================================

def render_weather_charts(df: pd.DataFrame):
    """Exibe gráficos de precipitação, umidade e vento."""

    st.subheader("Indicadores meteorológicos")

    st.caption(
        "Distribuição das condições meteorológicas no período."
    )

    coluna1, coluna2, coluna3 = st.columns(
        3,
        gap="large"
    )

    with coluna1:

        with st.container(border=True):

            st.markdown("**🌧️ Precipitação diária**")
            st.caption("Volume de chuva previsto (mm).")

            fig = px.bar(
                df,
                x="data_referencia",
                y="precipitacao_mm",
                color_discrete_sequence=["#38BDF8"],
                labels={
                    "data_referencia": "Data",
                    "precipitacao_mm": "Precipitação (mm)"
                }
            )

            fig.update_traces(
                marker_line_width=0,
                hovertemplate=(
                    "<b>%{x|%d/%m/%Y}</b><br>"
                    "Precipitação: %{y:.1f} mm"
                    "<extra></extra>"
                )
            )

            st.plotly_chart(
                configurar_grafico(fig),
                width="stretch",
                config={"displayModeBar": False}
            )

    with coluna2:

        with st.container(border=True):

            st.markdown("**💧 Umidade relativa**")
            st.caption("Umidade média do ar (%).")

            fig = px.area(
                df,
                x="data_referencia",
                y="umidade_media_pct",
                color_discrete_sequence=["#34D399"],
                labels={
                    "data_referencia": "Data",
                    "umidade_media_pct": "Umidade (%)"
                }
            )

            fig.update_traces(
                line_width=3,
                fillcolor="rgba(52,211,153,0.12)",
                hovertemplate=(
                    "<b>%{x|%d/%m/%Y}</b><br>"
                    "Umidade: %{y:.0f}%"
                    "<extra></extra>"
                )
            )

            fig = configurar_grafico(fig)
            fig.update_yaxes(range=[0, 100])

            st.plotly_chart(
                fig,
                width="stretch",
                config={"displayModeBar": False}
            )

    with coluna3:

        with st.container(border=True):

            st.markdown("**💨 Velocidade do vento**")
            st.caption("Velocidade máxima prevista (km/h).")

            fig = px.bar(
                df,
                x="data_referencia",
                y="vento_max_kmh",
                color_discrete_sequence=["#A78BFA"],
                labels={
                    "data_referencia": "Data",
                    "vento_max_kmh": "Vento (km/h)"
                }
            )

            fig.update_traces(
                marker_line_width=0,
                hovertemplate=(
                    "<b>%{x|%d/%m/%Y}</b><br>"
                    "Vento: %{y:.1f} km/h"
                    "<extra></extra>"
                )
            )

            st.plotly_chart(
                configurar_grafico(fig),
                width="stretch",
                config={"displayModeBar": False}
            )


# =====================================================
# TABELA DE PREVISÕES
# =====================================================

def render_data_table(df: pd.DataFrame):
    """Exibe os registros e permite exportar os dados."""

    st.subheader("Previsões detalhadas")

    st.caption(
        "Registros meteorológicos armazenados no banco."
    )

    colunas = {
        "data_referencia": "Data",
        "cidade": "Cidade",
        "estado": "UF",
        "temperatura_max_c": "Temp. máxima (°C)",
        "temperatura_min_c": "Temp. mínima (°C)",
        "precipitacao_mm": "Precipitação (mm)",
        "umidade_media_pct": "Umidade (%)",
        "vento_max_kmh": "Vento (km/h)"
    }

    tabela = df[
        list(colunas.keys())
    ].copy()

    tabela["condicao_climatica"] = (
        df["codigo_clima"].apply(
            lambda codigo: descrever_condicao(codigo)[1]
        )
    )

    tabela["data_referencia"] = (
        tabela["data_referencia"].dt.strftime("%d/%m/%Y")
    )

    tabela = tabela.rename(
        columns={
            **colunas,
            "condicao_climatica": "Condição do tempo"
        }
    )

    with st.container(border=True):

        st.dataframe(
            tabela,
            width="stretch",
            hide_index=True,
            height=320
        )

        csv = tabela.to_csv(
            index=False,
            sep=";",
            decimal=",",
            encoding="utf-8-sig"
        )

        st.download_button(
            label="↓ Exportar dados em CSV",
            data=csv,
            file_name="previsao_meteorologica.csv",
            mime="text/csv"
        )


# =====================================================
# RODAPÉ
# =====================================================

def render_footer():
    """Exibe as informações de autoria."""

    st.divider()

    st.caption(
        "CLIMA SP ANALYTICS | "
        "Python • Streamlit • Plotly • Pandas • MySQL"
    )

    st.caption(
        "Projeto pessoal de Kerlison Luan Andrade Lopes."
    )
