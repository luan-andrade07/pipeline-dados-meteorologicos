
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
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
    page_title="Clima Brasil | Analytics",
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
    render_footer,
    descrever_condicao,
    formatar_valor,
    configurar_grafico
)

# =====================================================
# CRITÉRIOS INTERNOS DOS ALERTAS
# =====================================================

CRITERIOS_ALERTAS = (
    {
        "evento": "Chuva significativa",
        "coluna": "precipitacao_mm",
        "unidade": "mm/dia",
        "atencao": 20.0,
        "elevado": 50.0
    },
    {
        "evento": "Calor elevado",
        "coluna": "temperatura_max_c",
        "unidade": "°C",
        "atencao": 33.0,
        "elevado": 38.0
    },
    {
        "evento": "Vento forte",
        "coluna": "vento_max_kmh",
        "unidade": "km/h",
        "atencao": 40.0,
        "elevado": 60.0
    }
)

COLUNAS_ALERTAS = [
    "Nível",
    "Cidade",
    "Data",
    "Evento",
    "Valor previsto",
    "Critério atingido"
]

VARIAVEIS_HISTORICO = {
    "Temperatura máxima": (
        "temperatura_max_c",
        "°C"
    ),
    "Temperatura mínima": (
        "temperatura_min_c",
        "°C"
    ),
    "Precipitação": (
        "precipitacao_mm",
        "mm"
    ),
    "Umidade relativa": (
        "umidade_media_pct",
        "%"
    ),
    "Velocidade máxima do vento": (
        "vento_max_kmh",
        "km/h"
    )
}

# =====================================================
# CARREGAMENTO DO CSS
# =====================================================

def carregar_estilo():
    """Carrega o arquivo CSS externo."""

    caminho_css = DASHBOARD_DIR / "style.css"

    try:
        css = caminho_css.read_text(
            encoding="utf-8"
        )

        st.markdown(
            f"<style>\n{css}\n</style>",
            unsafe_allow_html=True
        )

    except OSError:
        st.error(
            "Não foi possível carregar dashboard/style.css."
        )

# =====================================================
# CONEXÃO COM O MYSQL
# =====================================================

@st.cache_resource
def obter_engine():
    """Cria uma conexão reutilizável com o MySQL."""

    return criar_conexao()

# =====================================================
# CARREGAMENTO DAS PREVISÕES ATUAIS
# =====================================================

@st.cache_data(ttl=60)
def carregar_dados():
    """Consulta a tabela de previsões mais recentes."""

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
        df = pd.read_sql_query(
            comando_sql,
            conexao
        )

    if not df.empty:

        df["data_referencia"] = pd.to_datetime(
            df["data_referencia"],
            errors="coerce"
        )

        df["data_coleta"] = pd.to_datetime(
            df["data_coleta"],
            errors="coerce"
        )

        df = df.dropna(
            subset=["data_referencia"]
        )

    return df

# =====================================================
# NOVO: CARREGAMENTO DO HISTÓRICO
# =====================================================

@st.cache_data(ttl=60)
def carregar_historico():
    """
    Consulta todas as versões históricas das previsões.

    data_coleta_utc é armazenada no MySQL em UTC.
    A conversão para o horário de São Paulo ocorre
    apenas para apresentação no dashboard.
    """

    comando_sql = text("""
        SELECT
            id,
            cidade,
            estado,
            data_referencia,
            temperatura_max_c,
            temperatura_min_c,
            precipitacao_mm,
            umidade_media_pct,
            vento_max_kmh,
            codigo_clima,
            data_coleta_utc
        FROM clima_diario_historico
        ORDER BY
            cidade,
            estado,
            data_referencia,
            data_coleta_utc,
            id
    """)

    engine = obter_engine()

    with engine.connect() as conexao:
        df = pd.read_sql_query(
            comando_sql,
            conexao
        )

    if df.empty:
        return df

    df["data_referencia"] = pd.to_datetime(
        df["data_referencia"],
        errors="coerce"
    )

    # O MySQL armazena DATETIME sem informação
    # de fuso. Os valores desta coluna são UTC.
    df["data_coleta_utc"] = pd.to_datetime(
        df["data_coleta_utc"],
        errors="coerce",
        utc=True
    )

    df = df.dropna(
        subset=[
            "data_referencia",
            "data_coleta_utc"
        ]
    ).copy()

    df["data_coleta_local"] = (
        df["data_coleta_utc"]
        .dt.tz_convert("America/Sao_Paulo")
    )

    for coluna, _ in VARIAVEIS_HISTORICO.values():

        df[coluna] = pd.to_numeric(
            df[coluna],
            errors="coerce"
        )

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

    elif isinstance(periodo, date):

        resultado = resultado[
            resultado["data_referencia"].dt.date
            == periodo
        ]

    return resultado

# =====================================================
# ANÁLISE DOS ALERTAS METEOROLÓGICOS
# =====================================================

def gerar_alertas(df: pd.DataFrame) -> pd.DataFrame:
    """Identifica previsões acima dos limites internos."""

    if df.empty:
        return pd.DataFrame(
            columns=COLUNAS_ALERTAS
        )

    hoje = pd.Timestamp.now(
        tz="America/Sao_Paulo"
    ).date()

    dados = df.copy()

    dados["data_referencia"] = pd.to_datetime(
        dados["data_referencia"],
        errors="coerce"
    )

    dados = dados.dropna(
        subset=["data_referencia"]
    )

    dados = dados[
        dados["data_referencia"].dt.date >= hoje
    ].copy()

    if dados.empty:
        return pd.DataFrame(
            columns=COLUNAS_ALERTAS
        )

    dados = dados.sort_values(
        "data_coleta"
    ).drop_duplicates(
        subset=[
            "cidade",
            "estado",
            "data_referencia"
        ],
        keep="last"
    )

    ocorrencias = []

    for _, registro in dados.iterrows():

        for criterio in CRITERIOS_ALERTAS:

            valor = pd.to_numeric(
                registro[criterio["coluna"]],
                errors="coerce"
            )

            if pd.isna(valor):
                continue

            if valor < criterio["atencao"]:
                continue

            elevado = (
                valor >= criterio["elevado"]
            )

            limite = (
                criterio["elevado"]
                if elevado
                else criterio["atencao"]
            )

            ocorrencias.append({
                "Nível": (
                    "🔴 Elevado"
                    if elevado
                    else "🟡 Atenção"
                ),
                "Cidade": (
                    f"{registro['cidade']}/"
                    f"{registro['estado']}"
                ),
                "Data": (
                    registro["data_referencia"]
                    .strftime("%d/%m/%Y")
                ),
                "Evento": criterio["evento"],
                "Valor previsto": (
                    f"{valor:.1f} "
                    f"{criterio['unidade']}"
                ),
                "Critério atingido": (
                    f"≥ {limite:g} "
                    f"{criterio['unidade']}"
                ),
                "_prioridade": (
                    1 if elevado else 0
                ),
                "_data": registro[
                    "data_referencia"
                ]
            })

    if not ocorrencias:
        return pd.DataFrame(
            columns=COLUNAS_ALERTAS
        )

    alertas = pd.DataFrame(
        ocorrencias
    )

    alertas = alertas.sort_values(
        [
            "_prioridade",
            "_data",
            "Cidade",
            "Evento"
        ],
        ascending=[
            False,
            True,
            True,
            True
        ]
    )

    return alertas[
        COLUNAS_ALERTAS
    ].reset_index(drop=True)

# =====================================================
# PAINEL DE ALERTAS
# =====================================================

def render_alertas_meteorologicos(
    df: pd.DataFrame
):
    """Exibe os avisos das previsões futuras."""

    st.subheader(
        "🚨 Monitoramento meteorológico"
    )

    st.caption(
        "Avisos automáticos para as datas futuras "
        "dentro do período selecionado na barra lateral. "
        "Não são alertas oficiais."
    )

    hoje = pd.Timestamp.now(
        tz="America/Sao_Paulo"
    ).date()

    datas_futuras = (
        pd.to_datetime(
            df["data_referencia"],
            errors="coerce"
        ).dt.date >= hoje
    )

    if not datas_futuras.any():

        st.info(
            "O período selecionado não contém "
            "previsões futuras."
        )

        return

    alertas = gerar_alertas(df)

    total = len(alertas)

    elevados = int(
        (
            alertas["Nível"] == "🔴 Elevado"
        ).sum()
    )

    cidades = alertas[
        "Cidade"
    ].nunique()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Avisos identificados",
            total
        )

    with col2:
        st.metric(
            "Nível elevado",
            elevados
        )

    with col3:
        st.metric(
            "Cidades com avisos",
            cidades
        )

    if alertas.empty:

        st.success(
            "Nenhuma previsão ultrapassou "
            "os limites configurados para "
            "o período futuro selecionado."
        )

    else:

        if elevados:

            st.error(
                "Há previsões acima do nível elevado "
                "definido no projeto. Consulte também "
                "os órgãos meteorológicos oficiais."
            )

        else:

            st.warning(
                "Há previsões que merecem atenção "
                "conforme os critérios internos "
                "do projeto."
            )

        st.dataframe(
            alertas,
            hide_index=True,
            width="stretch"
        )

    with st.expander(
        "Como esses avisos são calculados?"
    ):

        st.write(
            "**Chuva diária:** atenção a partir "
            "de 20 mm; nível elevado a partir "
            "de 50 mm."
        )

        st.write(
            "**Temperatura máxima:** atenção "
            "a partir de 33 °C; nível elevado "
            "a partir de 38 °C."
        )

        st.write(
            "**Vento máximo:** atenção a partir "
            "de 40 km/h; nível elevado "
            "a partir de 60 km/h."
        )

        st.caption(
            "Os limites são ilustrativos. "
            "Este painel não substitui alertas "
            "do INMET ou da Defesa Civil."
        )

# =====================================================
# COMPARAÇÃO ENTRE CIDADES
# =====================================================

def render_comparativo_cidades(
    df: pd.DataFrame
):
    """Compara os dados meteorológicos de uma data."""

    st.subheader(
        "🌎 Comparativo entre cidades"
    )

    st.caption(
        "Compare as condições meteorológicas "
        "das cidades monitoradas em uma mesma data."
    )

    dados = df.copy()

    datas_disponiveis = sorted(
        dados["data_referencia"]
        .dt.date
        .dropna()
        .unique()
        .tolist()
    )

    if not datas_disponiveis:

        st.info(
            "Não existem datas disponíveis "
            "para comparação."
        )

        return

    hoje = pd.Timestamp.now(
        tz="America/Sao_Paulo"
    ).date()

    datas_futuras = [
        data
        for data in datas_disponiveis
        if data >= hoje
    ]

    if hoje in datas_disponiveis:

        data_padrao = hoje

    elif datas_futuras:

        data_padrao = datas_futuras[0]

    else:

        data_padrao = datas_disponiveis[-1]

    indice_padrao = datas_disponiveis.index(
        data_padrao
    )

    data_selecionada = st.selectbox(
        "Data da comparação",
        options=datas_disponiveis,
        index=indice_padrao,
        format_func=lambda data: data.strftime(
            "%d/%m/%Y"
        )
    )

    dados_dia = dados[
        dados["data_referencia"].dt.date
        == data_selecionada
    ].copy()

    dados_dia = dados_dia.sort_values(
        "data_coleta"
    ).drop_duplicates(
        subset=[
            "cidade",
            "estado",
            "data_referencia"
        ],
        keep="last"
    )

    dados_dia = dados_dia.sort_values(
        ["cidade", "estado"]
    )

    colunas_numericas = [
        "temperatura_max_c",
        "temperatura_min_c",
        "precipitacao_mm",
        "umidade_media_pct",
        "vento_max_kmh"
    ]

    for coluna in colunas_numericas:

        dados_dia[coluna] = pd.to_numeric(
            dados_dia[coluna],
            errors="coerce"
        )

    quantidade_cidades = len(
        dados_dia[
            ["cidade", "estado"]
        ].drop_duplicates()
    )

    st.caption(
        f"Data selecionada: "
        f"{data_selecionada.strftime('%d/%m/%Y')} "
        f"• {quantidade_cidades} cidade(s) com dados."
    )

    if quantidade_cidades < 2:

        st.info(
            "Há dados de apenas uma cidade nesta data. "
            "Selecione outra data para comparação."
        )

    # =============================================
    # INDICADORES GERAIS
    # =============================================

    st.subheader(
        "Visão geral das cidades"
    )

    media_maxima = dados_dia[
        "temperatura_max_c"
    ].mean()

    media_minima = dados_dia[
        "temperatura_min_c"
    ].mean()

    media_chuva = dados_dia[
        "precipitacao_mm"
    ].mean()

    maior_vento = dados_dia[
        "vento_max_kmh"
    ].max()

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            "🏙️ Cidades",
            quantidade_cidades
        )

    with col2:
        st.metric(
            "🌡️ Máxima média",
            formatar_valor(
                media_maxima,
                "°C"
            )
        )

    with col3:
        st.metric(
            "❄️ Mínima média",
            formatar_valor(
                media_minima,
                "°C"
            )
        )

    with col4:
        st.metric(
            "🌧️ Chuva média",
            formatar_valor(
                media_chuva,
                "mm"
            )
        )

    with col5:
        st.metric(
            "💨 Maior vento",
            formatar_valor(
                maior_vento,
                "km/h"
            )
        )

    # =============================================
    # COMPARAÇÃO DE TEMPERATURAS
    # =============================================

    st.subheader(
        "Comparação de temperaturas"
    )

    st.caption(
        "Temperaturas máximas e mínimas "
        "previstas para cada cidade."
    )

    with st.container(border=True):

        dados_temperatura = dados_dia.melt(
            id_vars=["cidade"],
            value_vars=[
                "temperatura_max_c",
                "temperatura_min_c"
            ],
            var_name="tipo_temperatura",
            value_name="temperatura"
        )

        dados_temperatura[
            "tipo_temperatura"
        ] = dados_temperatura[
            "tipo_temperatura"
        ].map({
            "temperatura_max_c": "Máxima",
            "temperatura_min_c": "Mínima"
        })

        fig_temperatura = px.bar(
            dados_temperatura,
            x="cidade",
            y="temperatura",
            color="tipo_temperatura",
            barmode="group",
            color_discrete_map={
                "Máxima": "#F59E0B",
                "Mínima": "#38BDF8"
            },
            labels={
                "cidade": "Cidade",
                "temperatura": "Temperatura (°C)",
                "tipo_temperatura": "Medição"
            }
        )

        st.plotly_chart(
            configurar_grafico(
                fig_temperatura
            ),
            width="stretch",
            config={
                "displayModeBar": False
            }
        )

    # =============================================
    # COMPARAÇÃO DE PRECIPITAÇÃO
    # =============================================

    st.subheader(
        "Comparação de precipitação"
    )

    st.caption(
        "Volume diário de chuva previsto por cidade."
    )

    with st.container(border=True):

        fig_chuva = px.bar(
            dados_dia,
            x="cidade",
            y="precipitacao_mm",
            color_discrete_sequence=[
                "#38BDF8"
            ],
            labels={
                "cidade": "Cidade",
                "precipitacao_mm": "Precipitação (mm)"
            }
        )

        st.plotly_chart(
            configurar_grafico(fig_chuva),
            width="stretch",
            config={
                "displayModeBar": False
            }
        )

    # =============================================
    # TABELA COMPARATIVA
    # =============================================

    st.subheader(
        "Resumo meteorológico por cidade"
    )

    tabela = dados_dia[
        [
            "cidade",
            "estado",
            "temperatura_max_c",
            "temperatura_min_c",
            "precipitacao_mm",
            "umidade_media_pct",
            "vento_max_kmh",
            "codigo_clima"
        ]
    ].copy()

    tabela["condicao"] = tabela[
        "codigo_clima"
    ].apply(
        lambda codigo: descrever_condicao(
            codigo
        )[1]
    )

    tabela = tabela.drop(
        columns=["codigo_clima"]
    )

    tabela = tabela.rename(
        columns={
            "cidade": "Cidade",
            "estado": "UF",
            "temperatura_max_c": "Máxima (°C)",
            "temperatura_min_c": "Mínima (°C)",
            "precipitacao_mm": "Chuva (mm)",
            "umidade_media_pct": "Umidade (%)",
            "vento_max_kmh": "Vento (km/h)",
            "condicao": "Condição do tempo"
        }
    )

    with st.container(border=True):

        st.dataframe(
            tabela,
            hide_index=True,
            width="stretch"
        )

# =====================================================
# NOVO: ANÁLISE HISTÓRICA DE PREVISÕES
# =====================================================

def render_historico_previsoes(
    df: pd.DataFrame,
    cidade: str,
    periodo
):
    """
    Permite acompanhar como uma previsão mudou
    entre diferentes execuções do pipeline.
    """

    st.divider()

    st.subheader(
        "📈 Evolução histórica das previsões"
    )

    st.caption(
        "Compare diferentes coletas para a mesma "
        "cidade e data de previsão. "
        "São versões de previsões meteorológicas, "
        "não medições observadas."
    )

    if df.empty:

        st.info(
            "O histórico ainda não possui registros."
        )

        return

    # Respeita os filtros da barra lateral
    dados = aplicar_filtros(
        df,
        cidade,
        periodo
    )

    if dados.empty:

        st.info(
            "Não existem registros históricos "
            "para os filtros selecionados."
        )

        return

    dados = dados.copy()

    dados["localidade"] = (
        dados["cidade"].astype(str)
        + "/"
        + dados["estado"].astype(str)
    )

    localidades = sorted(
        dados["localidade"]
        .dropna()
        .unique()
        .tolist()
    )

    # =============================================
    # SELEÇÃO DA CIDADE
    # =============================================

    cidade_historico = st.selectbox(
        "Cidade para análise histórica",
        options=localidades,
        key="historico_cidade"
    )

    dados_cidade = dados[
        dados["localidade"] == cidade_historico
    ].copy()

    # =============================================
    # SELEÇÃO DA DATA DA PREVISÃO
    # =============================================

    datas_disponiveis = sorted(
        dados_cidade["data_referencia"]
        .dt.date
        .dropna()
        .unique()
        .tolist()
    )

    if not datas_disponiveis:

        st.info(
            "Nenhuma data disponível no histórico."
        )

        return

    hoje = pd.Timestamp.now(
        tz="America/Sao_Paulo"
    ).date()

    datas_futuras = [
        data
        for data in datas_disponiveis
        if data >= hoje
    ]

    if hoje in datas_disponiveis:
        data_padrao = hoje

    elif datas_futuras:
        data_padrao = datas_futuras[0]

    else:
        data_padrao = datas_disponiveis[-1]

    data_previsao = st.selectbox(
        "Data da previsão que deseja acompanhar",
        options=datas_disponiveis,
        index=datas_disponiveis.index(
            data_padrao
        ),
        format_func=lambda data: data.strftime(
            "%d/%m/%Y"
        ),
        key="historico_data"
    )

    # Todas as coletas para uma mesma previsão
    evolucao = dados_cidade[
        dados_cidade["data_referencia"].dt.date
        == data_previsao
    ].copy()

    evolucao = evolucao.sort_values(
        ["data_coleta_utc", "id"]
    )

    if evolucao.empty:
        st.info(
            "Não há coletas para esta previsão."
        )
        return

    # =============================================
    # SELEÇÃO DO INDICADOR
    # =============================================

    nome_variavel = st.selectbox(
        "Indicador meteorológico",
        options=list(
            VARIAVEIS_HISTORICO.keys()
        ),
        key="historico_variavel"
    )

    coluna, unidade = VARIAVEIS_HISTORICO[
        nome_variavel
    ]

    primeira_previsao = evolucao.iloc[0]
    ultima_previsao = evolucao.iloc[-1]

    valor_inicial = primeira_previsao[coluna]
    valor_final = ultima_previsao[coluna]

    quantidade_coletas = len(evolucao)

    diferenca = None

    if (
        quantidade_coletas >= 2
        and pd.notna(valor_inicial)
        and pd.notna(valor_final)
    ):

        diferenca = (
            float(valor_final)
            - float(valor_inicial)
        )

    # =============================================
    # INDICADORES DA EVOLUÇÃO
    # =============================================

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Coletas registradas",
            quantidade_coletas
        )

    with col2:
        st.metric(
            "Primeira previsão",
            formatar_valor(
                valor_inicial,
                unidade
            )
        )

    with col3:

        st.metric(
            "Previsão mais recente",
            formatar_valor(
                valor_final,
                unidade
            ),
            delta=(
                f"{diferenca:+.1f} {unidade}"
                if diferenca is not None
                else None
            ),
            delta_color="off"
        )

    # =============================================
    # GRÁFICO DE EVOLUÇÃO
    # =============================================

    if quantidade_coletas < 2:

        st.info(
            "Esta previsão possui apenas uma coleta "
            "histórica. Após uma nova execução do "
            "pipeline, será possível visualizar "
            "sua evolução ao longo do tempo."
        )

    else:

        st.subheader(
            f"Evolução de {nome_variavel.lower()}"
        )

        st.caption(
            f"Previsão para "
            f"{data_previsao.strftime('%d/%m/%Y')} "
            f"em {cidade_historico}."
        )

        with st.container(border=True):

            fig = px.line(
                evolucao,
                x="data_coleta_local",
                y=coluna,
                markers=True,
                labels={
                    "data_coleta_local":
                        "Data e hora da coleta",
                    coluna:
                        f"{nome_variavel} ({unidade})"
                }
            )

            fig.update_traces(
                line_width=3,
                marker_size=9
            )

            fig = configurar_grafico(fig)

            st.plotly_chart(
                fig,
                width="stretch",
                config={
                    "displayModeBar": False
                }
            )

    # =============================================
    # TABELA COM TODAS AS COLETAS
    # =============================================

    st.subheader(
        "Histórico detalhado das coletas"
    )

    tabela = evolucao[
        [
            "data_coleta_local",
            "temperatura_max_c",
            "temperatura_min_c",
            "precipitacao_mm",
            "umidade_media_pct",
            "vento_max_kmh"
        ]
    ].copy()

    tabela["data_coleta_local"] = (
        tabela["data_coleta_local"]
        .dt.strftime("%d/%m/%Y %H:%M:%S")
    )

    tabela = tabela.rename(
        columns={
            "data_coleta_local":
                "Data/hora da coleta (Brasília)",
            "temperatura_max_c":
                "Máxima (°C)",
            "temperatura_min_c":
                "Mínima (°C)",
            "precipitacao_mm":
                "Chuva (mm)",
            "umidade_media_pct":
                "Umidade (%)",
            "vento_max_kmh":
                "Vento (km/h)"
        }
    )

    with st.container(border=True):

        st.dataframe(
            tabela,
            hide_index=True,
            width="stretch"
        )

    st.caption(
        "Cada linha corresponde a uma execução "
        "do pipeline que consultou essa cidade "
        "e essa data de previsão. "
        "Os horários são exibidos no fuso "
        "America/Sao_Paulo."
    )

# =====================================================
# EXECUÇÃO PRINCIPAL
# =====================================================

def main():
    """Coordena a apresentação do dashboard."""

    carregar_estilo()

    # =============================================
    # CARREGAMENTO DAS PREVISÕES
    # =============================================

    try:

        with st.spinner(
            "Consultando banco de dados..."
        ):
            df = carregar_dados()

    except (SQLAlchemyError, ValueError):

        st.error(
            "Não foi possível acessar "
            "o banco de dados MySQL."
        )

        st.caption(
            "Verifique se o MySQL está em execução "
            "e se as configurações do arquivo .env "
            "estão corretas."
        )

        st.stop()

    except Exception as erro:

        st.error(
            "Ocorreu um erro inesperado "
            "ao carregar os dados."
        )

        st.exception(erro)
        st.stop()

    if df.empty:

        st.warning(
            "Nenhum registro encontrado. "
            "Execute o pipeline ETL antes "
            "de abrir o dashboard."
        )

        st.stop()

    # =============================================
    # FILTROS
    # =============================================

    cidade, periodo, atualizar = render_sidebar(df)

    if atualizar:

        carregar_dados.clear()
        carregar_historico.clear()

        st.rerun()

    df_filtrado = aplicar_filtros(
        df,
        cidade,
        periodo
    )

    if df_filtrado.empty:

        st.warning(
            "Não existem registros para "
            "os filtros selecionados."
        )

        st.stop()

    cidade_atual = (
        "Todas as cidades"
        if cidade == "Todas"
        else cidade
    )

    render_header(
        cidade_atual
    )

    # =============================================
    # ALERTAS METEOROLÓGICOS
    # =============================================

    render_alertas_meteorologicos(
        df_filtrado
    )

    # =============================================
    # VISÃO GERAL DAS CIDADES
    # =============================================

    if cidade == "Todas":

        render_comparativo_cidades(
            df_filtrado
        )

        st.subheader(
            "Histórico de previsões"
        )

        render_data_table(
            df_filtrado
        )

    # =============================================
    # VISÃO INDIVIDUAL DA CIDADE
    # =============================================

    else:

        render_current_forecast(
            df_filtrado
        )

        render_metrics(
            df_filtrado
        )

        render_temperature_chart(
            df_filtrado
        )

        render_weather_charts(
            df_filtrado
        )

        render_data_table(
            df_filtrado
        )

    # =============================================
    # NOVO: HISTÓRICO DAS COLETAS
    # =============================================

    try:

        with st.spinner(
            "Consultando histórico de previsões..."
        ):
            df_historico = carregar_historico()

        render_historico_previsoes(
            df_historico,
            cidade,
            periodo
        )

    except (SQLAlchemyError, ValueError):

        st.warning(
            "Não foi possível consultar o histórico "
            "das previsões no MySQL."
        )

    except Exception as erro:

        st.warning(
            "Ocorreu um problema ao apresentar "
            "a evolução histórica."
        )

        st.exception(erro)

    # =============================================
    # RODAPÉ
    # =============================================

    render_footer()

if __name__ == "__main__":
    main()