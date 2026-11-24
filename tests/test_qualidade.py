
"""Testes da análise de qualidade dos dados."""

from datetime import timedelta

import pandas as pd

from src.quality import analisar_qualidade


AGORA = pd.Timestamp(
    "2026-11-24T15:00:00Z"
)

CIDADES = [
    {
        "cidade": "São Paulo",
        "estado": "SP"
    }
]


# =====================================================
# DADOS SIMULADOS
# =====================================================

def registros_validos():

    hoje = AGORA.tz_convert(
        "America/Sao_Paulo"
    ).date()

    return pd.DataFrame([
        {
            "cidade": "São Paulo",
            "estado": "SP",
            "data_referencia": (
                hoje + timedelta(days=i)
            ),
            "temperatura_max_c": 28.0,
            "temperatura_min_c": 20.0,
            "precipitacao_mm": 5.0,
            "umidade_media_pct": 60.0,
            "vento_max_kmh": 10.0,
            "codigo_clima": 2,
            "coleta_utc": (
                AGORA - pd.Timedelta(hours=3)
            )
        }
        for i in range(7)
    ])


# =====================================================
# TESTE 1 — DADOS COMPLETOS
# =====================================================

def test_qualidade_dados_completos():

    resumo, problemas = analisar_qualidade(
        registros_validos(),
        CIDADES,
        agora=AGORA
    )

    assert resumo.iloc[0]["Status"] == "OK"

    assert resumo.iloc[0]["Dias presentes"] == 7

    assert problemas.empty


# =====================================================
# TESTE 2 — PREVISÃO AUSENTE
# =====================================================

def test_qualidade_encontra_dia_ausente():

    dados = registros_validos().iloc[:-1]

    resumo, problemas = analisar_qualidade(
        dados,
        CIDADES,
        agora=AGORA
    )

    assert resumo.iloc[0]["Datas ausentes"] == 1

    assert resumo.iloc[0]["Status"] == "CRÍTICO"

    assert (
        problemas["Problema"] == "Previsão ausente"
    ).sum() == 1


# =====================================================
# TESTE 3 — DADOS DESATUALIZADOS
# =====================================================

def test_qualidade_distingue_dado_desatualizado():

    dados = registros_validos()

    dados["coleta_utc"] = (
        AGORA - pd.Timedelta(hours=40)
    )

    resumo, _ = analisar_qualidade(
        dados,
        CIDADES,
        agora=AGORA
    )

    assert resumo.iloc[0]["Status"] == "ATENÇÃO"

    dados["coleta_utc"] = (
        AGORA - pd.Timedelta(hours=80)
    )

    resumo, _ = analisar_qualidade(
        dados,
        CIDADES,
        agora=AGORA
    )

    assert resumo.iloc[0]["Status"] == "CRÍTICO"


# =====================================================
# TESTE 4 — REGISTRO INCONSISTENTE
# =====================================================

def test_qualidade_detecta_registro_invalido():

    dados = registros_validos()

    dados.loc[
        0,
        "temperatura_min_c"
    ] = 40

    resumo, problemas = analisar_qualidade(
        dados,
        CIDADES,
        agora=AGORA
    )

    assert (
        resumo.iloc[0]["Registros inconsistentes"]
        == 1
    )

    assert (
        problemas["Problema"]
        == "Registro inconsistente"
    ).sum() == 1


# =====================================================
# TESTE 5 — CIDADE SEM DADOS
# =====================================================

def test_qualidade_detecta_cidade_sem_dados():

    dados = registros_validos()

    cidades = CIDADES + [
        {
            "cidade": "Recife",
            "estado": "PE"
        }
    ]

    resumo, problemas = analisar_qualidade(
        dados,
        cidades,
        agora=AGORA
    )

    recife = resumo[
        resumo["Cidade"] == "Recife"
    ].iloc[0]

    assert recife["Datas ausentes"] == 7

    assert recife["Status"] == "CRÍTICO"

    assert (
        problemas["Cidade"] == "Recife/PE"
    ).sum() == 8
