
import sys
from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError


# =====================================================
# CONFIGURAÇÃO DA PÁGINA
# =====================================================

ROOT_DIR = Path(__file__).resolve().parents[2]
DASHBOARD_DIR = ROOT_DIR / "dashboard"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")

st.set_page_config(
    page_title="Mapa Meteorológico | Clima Brasil",
    page_icon="🗺️",
    layout="wide"
)

from src.extract import CIDADES
from src.load import criar_conexao
from dashboard.components import descrever_condicao, formatar_valor


# =====================================================
# CONFIGURAÇÃO DOS INDICADORES E AVISOS
# =====================================================

INDICADORES = {
    "Temperatura máxima": ("temperatura_max_c", "°C"),
    "Temperatura mínima": ("temperatura_min_c", "°C"),
    "Precipitação": ("precipitacao_mm", "mm"),
    "Umidade relativa": ("umidade_media_pct", "%"),
    "Vento máximo": ("vento_max_kmh", "km/h")
}

# Os valores abaixo são critérios internos do projeto,
# não alertas meteorológicos oficiais.
CRITERIOS = (
    ("Chuva", "precipitacao_mm", "mm", 20, 50),
    ("Calor", "temperatura_max_c", "°C", 33, 38),
    ("Vento", "vento_max_kmh", "km/h", 40, 60)
)

CORES = {
    "Sem aviso": [52, 211, 153, 210],
    "Atenção": [250, 204, 21, 225],
    "Elevado": [248, 113, 113, 235]
}


# =====================================================
# ESTILO E CONSULTA AOS DADOS
# =====================================================

def carregar_estilo():
    """Reutiliza o estilo do dashboard principal."""
    try:
        css = (DASHBOARD_DIR / "style.css").read_text(
            encoding="utf-8"
        )
        st.markdown(f"<style>\n{css}\n</style>", unsafe_allow_html=True)
    except OSError:
        st.warning("Não foi possível carregar o estilo do dashboard.")


@st.cache_data(ttl=60)
def carregar_previsoes():
    """Lê a previsão mais recente de cada cidade e data."""
    consulta = text("""
        SELECT
            cidade, estado, data_referencia,
            temperatura_max_c, temperatura_min_c,
            precipitacao_mm, umidade_media_pct,
            vento_max_kmh, codigo_clima, data_coleta
        FROM clima_diario
        ORDER BY data_referencia, cidade
    """)

    engine = criar_conexao()
    try:
        with engine.connect() as conexao:
            dados = pd.read_sql_query(consulta, conexao)
    finally:
        engine.dispose()

    if dados.empty:
        return dados

    dados["data_referencia"] = pd.to_datetime(
        dados["data_referencia"], errors="coerce"
    )
    dados["data_coleta"] = pd.to_datetime(
        dados["data_coleta"], errors="coerce"
    )
    dados = dados.dropna(subset=["data_referencia"])

    for coluna, _ in INDICADORES.values():
        dados[coluna] = pd.to_numeric(dados[coluna], errors="coerce")

    return dados


# =====================================================
# CLASSIFICAÇÃO DAS CONDIÇÕES
# =====================================================

def classificar_previsao(registro):
    """Calcula o nível mais alto entre os critérios internos."""
    prioridade = 0
    motivos = []

    for evento, coluna, unidade, atencao, elevado in CRITERIOS:
        valor = registro.get(coluna)
        if pd.isna(valor):
            continue

        if valor >= elevado:
            prioridade = 2
            motivos.append(f"{evento}: {valor:.1f} {unidade} (elevado)")
        elif valor >= atencao:
            prioridade = max(prioridade, 1)
            motivos.append(f"{evento}: {valor:.1f} {unidade} (atenção)")

    nivel = {0: "Sem aviso", 1: "Atenção", 2: "Elevado"}[prioridade]
    return nivel, "; ".join(motivos) or "Nenhum limite atingido", prioridade


def preparar_mapa(df):
    """Associa as coordenadas cadastradas às previsões."""
    cidades = pd.DataFrame(CIDADES).rename(
        columns={"latitude": "lat", "longitude": "lon"}
    )

    mapa = df.merge(
        cidades[["cidade", "estado", "lat", "lon"]],
        on=["cidade", "estado"],
        how="inner",
        validate="many_to_one"
    ).copy()

    if mapa.empty:
        return mapa

    mapa = mapa.sort_values("data_coleta").drop_duplicates(
        subset=["cidade", "estado", "data_referencia"],
        keep="last"
    )

    classificacoes = [
        classificar_previsao(registro)
        for registro in mapa.to_dict(orient="records")
    ]
    mapa["nivel"] = [item[0] for item in classificacoes]
    mapa["motivos"] = [item[1] for item in classificacoes]
    mapa["prioridade"] = [item[2] for item in classificacoes]
    mapa["cor"] = mapa["nivel"].map(CORES)

    mapa["localidade"] = mapa["cidade"] + "/" + mapa["estado"]
    mapa["condicao"] = mapa["codigo_clima"].apply(
        lambda codigo: descrever_condicao(codigo)[1]
    )

    for nome, (coluna, unidade) in INDICADORES.items():
        mapa[coluna + "_texto"] = mapa[coluna].apply(
            lambda valor: formatar_valor(valor, unidade)
        )

    return mapa


def calcular_raios(mapa, coluna):
    """Aumenta os marcadores conforme o indicador escolhido."""
    valores = mapa[coluna]
    minimo, maximo = valores.min(), valores.max()

    if pd.notna(minimo) and pd.notna(maximo) and maximo > minimo:
        tamanhos = 30000 + (valores - minimo) / (maximo - minimo) * 50000
        return tamanhos.fillna(30000)

    return pd.Series(48000, index=mapa.index, dtype=float)


# =====================================================
# EXIBIÇÃO DA PÁGINA
# =====================================================

def main():
    carregar_estilo()
    st.title("🗺️ Mapa meteorológico do Brasil")
    st.caption(
        "Previsões da Open-Meteo armazenadas no MySQL. "
        "Escolha a data e passe o mouse nos marcadores para ver os detalhes."
    )

    with st.sidebar:
        st.subheader("🗺️ Mapa meteorológico")
        if st.button("↻ Atualizar dados do mapa", use_container_width=True):
            carregar_previsoes.clear()
            st.rerun()

    try:
        with st.spinner("Carregando previsões do MySQL..."):
            dados = carregar_previsoes()
    except (SQLAlchemyError, ValueError) as erro:
        st.error("Não foi possível consultar as previsões no MySQL.")
        st.caption(str(erro))
        st.stop()

    if dados.empty:
        st.warning("Não há previsões no banco. Execute python main.py.")
        st.stop()

    datas = sorted(dados["data_referencia"].dt.date.unique().tolist())
    hoje = pd.Timestamp.now(tz="America/Sao_Paulo").date()
    futuras = [data for data in datas if data >= hoje]
    data_padrao = hoje if hoje in datas else (
        futuras[0] if futuras else datas[-1]
    )

    coluna_data, coluna_indicador = st.columns(2)
    with coluna_data:
        data_escolhida = st.selectbox(
            "Data da previsão",
            options=datas,
            index=datas.index(data_padrao),
            format_func=lambda dia: dia.strftime("%d/%m/%Y")
        )

    with coluna_indicador:
        indicador = st.selectbox(
            "Tamanho dos marcadores conforme",
            options=list(INDICADORES.keys()),
            index=0
        )

    dados_dia = dados[
        dados["data_referencia"].dt.date == data_escolhida
    ].copy()

    mapa = preparar_mapa(dados_dia)
    if mapa.empty:
        st.warning("Não há previsões com coordenadas cadastradas para esta data.")
        st.stop()

    coluna_indicador_nome, unidade = INDICADORES[indicador]
    mapa["raio_m"] = calcular_raios(mapa, coluna_indicador_nome)

    if data_escolhida < hoje:
        st.info("A data escolhida está no passado: esta é uma previsão arquivada.")

    total = len(mapa)
    atencao = int((mapa["nivel"] == "Atenção").sum())
    elevado = int((mapa["nivel"] == "Elevado").sum())

    a, b, c, d = st.columns(4)
    a.metric("🏙️ Cidades no mapa", total)
    b.metric("🟡 Em atenção", atencao)
    c.metric("🔴 Nível elevado", elevado)
    d.metric("🌡️ Maior temperatura", formatar_valor(
        mapa["temperatura_max_c"].max(), "°C"
    ))

    st.caption(
        "🟢 Sem aviso  •  🟡 Atenção  •  🔴 Elevado  |  "
        "Cores calculadas para a data selecionada usando limites internos. "
        "Não representam alertas oficiais."
    )

    camada = pdk.Layer(
        "ScatterplotLayer",
        data=mapa[
            ["lat", "lon", "localidade", "nivel", "motivos",
             "condicao", "cor", "raio_m", "temperatura_max_c_texto",
             "temperatura_min_c_texto", "precipitacao_mm_texto",
             "umidade_media_pct_texto", "vento_max_kmh_texto"]
        ].to_dict(orient="records"),
        get_position="[lon, lat]",
        get_fill_color="cor",
        get_radius="raio_m",
        radius_min_pixels=9,
        radius_max_pixels=32,
        get_line_color=[255, 255, 255, 235],
        line_width_min_pixels=1,
        stroked=True,
        filled=True,
        pickable=True,
        auto_highlight=True
    )

    mapa_interativo = pdk.Deck(
        map_style=None,
        initial_view_state=pdk.ViewState(
            latitude=-15.2,
            longitude=-51.5,
            zoom=3.25,
            pitch=0
        ),
        layers=[camada],
        tooltip={
            "html": (
                "<b>{localidade}</b><br/>"
                "Condição: {condicao}<br/>"
                "Máxima: {temperatura_max_c_texto}<br/>"
                "Mínima: {temperatura_min_c_texto}<br/>"
                "Chuva: {precipitacao_mm_texto}<br/>"
                "Umidade: {umidade_media_pct_texto}<br/>"
                "Vento: {vento_max_kmh_texto}<br/>"
                "Classificação: <b>{nivel}</b><br/>"
                "{motivos}"
            ),
            "style": {"backgroundColor": "#142237", "color": "white"}
        }
    )

    st.pydeck_chart(
        mapa_interativo,
        height=540,
        width="stretch"
    )

    st.subheader("📋 Previsões das cidades no mapa")
    tabela = mapa.sort_values(
        ["prioridade", "cidade"], ascending=[False, True]
    )[
        ["cidade", "estado", "temperatura_max_c", "temperatura_min_c",
         "precipitacao_mm", "umidade_media_pct", "vento_max_kmh",
         "condicao", "nivel", "motivos"]
    ].rename(columns={
        "cidade": "Cidade",
        "estado": "UF",
        "temperatura_max_c": "Máxima (°C)",
        "temperatura_min_c": "Mínima (°C)",
        "precipitacao_mm": "Chuva (mm)",
        "umidade_media_pct": "Umidade (%)",
        "vento_max_kmh": "Vento (km/h)",
        "condicao": "Condição do tempo",
        "nivel": "Nível interno",
        "motivos": "Critérios atingidos"
    })

    st.dataframe(tabela, hide_index=True, width="stretch")

    with st.expander("Entenda os níveis de atenção"):
        st.write(
            "**Chuva:** atenção ≥ 20 mm/dia; elevado ≥ 50 mm/dia.  "
            "**Calor:** atenção ≥ 33 °C; elevado ≥ 38 °C.  "
            "**Vento:** atenção ≥ 40 km/h; elevado ≥ 60 km/h."
        )
        st.caption(
            "Esses limites são exemplos configuráveis no código. "
            "O mapa não substitui os avisos do INMET ou da Defesa Civil. "
            "O tamanho das bolhas muda com o indicador; a cor indica o nível interno."
        )


if __name__ == "__main__":
    main()
