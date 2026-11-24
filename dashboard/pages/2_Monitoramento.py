
"""Painel de acompanhamento das execuções do ETL."""

import sys
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

ROOT_DIR = Path(__file__).resolve().parents[2]
DASHBOARD_DIR = ROOT_DIR / "dashboard"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")

st.set_page_config(
    page_title="Monitoramento ETL | Clima Brasil",
    page_icon="📊",
    layout="wide"
)

from src.load import criar_conexao
from dashboard.components import configurar_grafico

# =====================================================
# CARREGAMENTO DAS EXECUÇÕES
# =====================================================

@st.cache_data(ttl=60)
def carregar_execucoes():
    """Consulta as últimas 100 execuções registradas."""

    consulta = text("""
        SELECT
            id,
            inicio_utc,
            fim_utc,
            duracao_seg,
            status,
            cidades_total,
            cidades_sucesso,
            cidades_falha,
            registros_processados
        FROM pipeline_execucoes
        ORDER BY id DESC
        LIMIT 100
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

    if dados.empty:
        return dados

    for coluna in (
        "inicio_utc",
        "fim_utc"
    ):

        dados[coluna] = pd.to_datetime(
            dados[coluna],
            errors="coerce",
            utc=True
        ).dt.tz_convert(
            "America/Sao_Paulo"
        )

    dados["duracao_seg"] = pd.to_numeric(
        dados["duracao_seg"],
        errors="coerce"
    )

    return dados

# =====================================================
# CARREGAMENTO DO DETALHAMENTO POR CIDADE
# =====================================================

@st.cache_data(ttl=60)
def carregar_cidades_execucao(
    execucao_id: int
):
    """Consulta o resultado de cada cidade."""

    consulta = text("""
        SELECT
            cidade,
            estado,
            status,
            etapa_falha,
            mensagem,
            registros_processados,
            duracao_seg
        FROM pipeline_execucao_cidades
        WHERE execucao_id = :execucao_id
        ORDER BY cidade, estado
    """)

    engine = criar_conexao()

    try:

        with engine.connect() as conexao:

            dados = pd.read_sql_query(
                consulta,
                conexao,
                params={
                    "execucao_id": execucao_id
                }
            )

    finally:
        engine.dispose()

    return dados

# =====================================================
# FORMATAÇÃO DE HORÁRIOS
# =====================================================

def formatar_horario(data):
    """Formata datas para apresentação."""

    if pd.isna(data):
        return "Não disponível"

    return data.strftime(
        "%d/%m/%Y %H:%M:%S"
    )

# =====================================================
# PÁGINA DE MONITORAMENTO
# =====================================================

def main():

    st.title(
        "📊 Monitoramento do pipeline ETL"
    )

    st.caption(
        "Execuções do pipeline de coleta meteorológica. "
        "Horários exibidos em America/Sao_Paulo."
    )

    # =============================================
    # ATUALIZAÇÃO
    # =============================================

    with st.sidebar:

        if st.button(
            "↻ Atualizar monitoramento",
            use_container_width=True
        ):

            carregar_execucoes.clear()
            carregar_cidades_execucao.clear()

            st.rerun()

    # =============================================
    # CONSULTA DAS EXECUÇÕES
    # =============================================

    try:

        with st.spinner(
            "Consultando histórico de execuções..."
        ):

            execucoes = carregar_execucoes()

    except (
        SQLAlchemyError,
        ValueError,
        OSError
    ):

        st.error(
            "Não foi possível consultar o monitoramento no MySQL."
        )

        st.info(
            "Verifique a conexão e execute "
            "'python main.py' pelo menos uma vez "
            "após instalar o módulo de monitoramento."
        )

        st.stop()

    if execucoes.empty:

        st.info(
            "Ainda não existem execuções registradas "
            "no monitoramento."
        )

        st.stop()

    ultima = execucoes.iloc[0]

    status = ultima["status"]

    # =============================================
    # RESUMO DA ÚLTIMA EXECUÇÃO
    # =============================================

    st.subheader(
        "Última execução"
    )

    a, b, c, d = st.columns(4)

    with a:
        st.metric(
            "Situação",
            str(status).replace(
                "_",
                " "
            ).title()
        )

    with b:
        st.metric(
            "Cidades processadas",
            (
                f"{int(ultima['cidades_sucesso'])}/"
                f"{int(ultima['cidades_total'])}"
            )
        )

    with c:
        st.metric(
            "Registros gravados/atualizados",
            int(
                ultima["registros_processados"]
            )
        )

    with d:

        duracao = ultima["duracao_seg"]

        st.metric(
            "Duração",
            (
                f"{duracao:.1f} s"
                if pd.notna(duracao)
                else "Em andamento"
            )
        )

    st.caption(
        f"Início: {formatar_horario(ultima['inicio_utc'])}"
        f"  |  "
        f"Fim: {formatar_horario(ultima['fim_utc'])}"
    )

    # =============================================
    # INTERPRETAÇÃO DO RESULTADO
    # =============================================

    if status == "SUCESSO":

        st.success(
            "Todas as cidades foram processadas "
            "na última execução registrada."
        )

    elif status == "PARCIAL":

        st.warning(
            "A última execução teve falhas "
            "em uma ou mais cidades."
        )

    elif status == "FALHA":

        st.error(
            "Nenhuma cidade foi processada "
            "com sucesso na última execução."
        )

    else:

        inicio = ultima["inicio_utc"]

        if pd.notna(inicio):

            minutos = (
                pd.Timestamp.now(
                    tz="America/Sao_Paulo"
                ) - inicio
            ).total_seconds() / 60

            if minutos > 30:

                st.warning(
                    "Essa execução permanece como "
                    "'Em execução' há mais de "
                    "30 minutos. Ela pode ter sido "
                    "interrompida. Confira "
                    "logs/pipeline.log."
                )

            else:

                st.info(
                    "Há uma execução iniciada "
                    "ainda sem resultado final registrado."
                )

    # =============================================
    # GRÁFICO DE DESEMPENHO
    # =============================================

    finalizadas = execucoes[
        execucoes["status"].isin([
            "SUCESSO",
            "PARCIAL",
            "FALHA"
        ])
    ].head(30).sort_values(
        "inicio_utc"
    )

    st.subheader(
        "Duração das últimas execuções"
    )

    if finalizadas.empty:

        st.info(
            "Ainda não há execuções concluídas "
            "para mostrar no gráfico."
        )

    else:

        fig = px.bar(
            finalizadas,
            x="inicio_utc",
            y="duracao_seg",
            color="status",
            color_discrete_map={
                "SUCESSO": "#34D399",
                "PARCIAL": "#FBBF24",
                "FALHA": "#FB7185"
            },
            labels={
                "inicio_utc": "Início da execução",
                "duracao_seg": "Duração (segundos)",
                "status": "Resultado"
            }
        )

        st.plotly_chart(
            configurar_grafico(fig),
            width="stretch",
            config={
                "displayModeBar": False
            }
        )

    # =============================================
    # TABELA DO HISTÓRICO
    # =============================================

    st.subheader(
        "Histórico das execuções"
    )

    tabela = execucoes.copy()

    for coluna in (
        "inicio_utc",
        "fim_utc"
    ):

        tabela[coluna] = tabela[
            coluna
        ].apply(
            formatar_horario
        )

    tabela = tabela.rename(
        columns={
            "id": "ID",
            "inicio_utc": "Início (Brasília)",
            "fim_utc": "Fim (Brasília)",
            "duracao_seg": "Duração (s)",
            "status": "Status",
            "cidades_total": "Cidades configuradas",
            "cidades_sucesso": "Sucessos",
            "cidades_falha": "Falhas",
            "registros_processados": "Registros"
        }
    )

    st.dataframe(
        tabela,
        hide_index=True,
        width="stretch"
    )

    # =============================================
    # DETALHAMENTO POR CIDADE
    # =============================================

    st.subheader(
        "Detalhamento por cidade"
    )

    opcoes = execucoes[
        "id"
    ].astype(int).tolist()

    etiquetas = {
        int(row["id"]): (
            f"#{int(row['id'])} — "
            f"{formatar_horario(row['inicio_utc'])} — "
            f"{row['status']}"
        )
        for _, row in execucoes.iterrows()
    }

    selecionado = st.selectbox(
        "Selecione uma execução",
        options=opcoes,
        format_func=lambda numero: etiquetas[numero]
    )

    try:

        detalhes = carregar_cidades_execucao(
            int(selecionado)
        )

    except (
        SQLAlchemyError,
        ValueError,
        OSError
    ):

        st.error(
            "Não foi possível consultar "
            "os resultados por cidade."
        )

        return

    if detalhes.empty:

        st.info(
            "Esta execução ainda não possui "
            "resultados por cidade registrados."
        )

    else:

        detalhes = detalhes.rename(
            columns={
                "cidade": "Cidade",
                "estado": "UF",
                "status": "Status",
                "etapa_falha": "Etapa da falha",
                "mensagem": "Detalhe",
                "registros_processados": "Registros",
                "duracao_seg": "Duração (s)"
            }
        )

        st.dataframe(
            detalhes,
            hide_index=True,
            width="stretch"
        )

    st.caption(
        "Este painel apresenta execuções registradas "
        "pelo Python. Não informa se o Windows está "
        "ligado nem confirma futuros disparos "
        "do Agendador de Tarefas."
    )

# =====================================================
# INICIALIZAÇÃO
# =====================================================

if __name__ == "__main__":
    main()