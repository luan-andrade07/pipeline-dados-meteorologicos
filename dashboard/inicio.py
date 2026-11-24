
import streamlit as st


# =====================================================
# PÁGINAS DO SISTEMA
# =====================================================

pagina_principal = st.Page(
    "app.py",
    title="Painel Principal",
    icon=":material/dashboard:",
    default=True
)

pagina_mapa = st.Page(
    "pages/1_Mapa_Meteorologico.py",
    title="Mapa do Brasil",
    icon=":material/map:"
)

pagina_monitoramento = st.Page(
    "pages/2_Monitoramento.py",
    title="Monitoramento ETL",
    icon=":material/monitor_heart:"
)

pagina_qualidade = st.Page(
    "pages/3_Qualidade_Dados.py",
    title="Qualidade dos Dados",
    icon=":material/verified_user:"
)


# =====================================================
# NAVEGAÇÃO SUPERIOR
# =====================================================

pagina = st.navigation(
    [
        pagina_principal,
        pagina_mapa,
        pagina_monitoramento,
        pagina_qualidade
    ],
    position="top"
)


# =====================================================
# EXECUÇÃO DA PÁGINA SELECIONADA
# =====================================================

pagina.run()
