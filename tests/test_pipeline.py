
"""Testes unitários do pipeline meteorológico."""

from contextlib import nullcontext
from datetime import timedelta

import pandas as pd
import pytest
import requests

from sqlalchemy.exc import SQLAlchemyError

from src import extract, load, transform
from dashboard.app import gerar_alertas

# =====================================================
# DADOS SIMULADOS PARA OS TESTES
# =====================================================

def resposta_api_valida():
    """Simula uma resposta diária da Open-Meteo."""

    return {
        "daily": {
            "time": [
                "2026-11-23",
                "2026-11-24"
            ],
            "temperature_2m_max": [29.0, 30.0],
            "temperature_2m_min": [21.0, 22.0],
            "precipitation_sum": [5.0, 10.0],
            "relative_humidity_2m_mean": [75, 80],
            "wind_speed_10m_max": [12.0, 15.0],
            "weather_code": [2, 61]
        }
    }

def registro_valido(**alteracoes):
    """Cria um registro meteorológico válido."""

    registro = {
        "cidade": "São Paulo",
        "estado": "SP",
        "data_referencia": "2026-11-23",
        "temperatura_max_c": 29.0,
        "temperatura_min_c": 21.0,
        "precipitacao_mm": 5.0,
        "umidade_media_pct": 75.0,
        "vento_max_kmh": 12.0,
        "codigo_clima": 2
    }

    registro.update(alteracoes)
    return registro

# =====================================================
# TESTES DA EXTRAÇÃO
# =====================================================

def test_api_valida_retorna_dados_diarios():

    diario = extract.validar_resposta_api(
        resposta_api_valida()
    )

    assert len(diario["time"]) == 2

    assert diario["temperature_2m_max"] == [
        29.0, 30.0
    ]

def test_api_rejeita_campos_ausentes():

    resposta = resposta_api_valida()

    del resposta["daily"]["weather_code"]

    with pytest.raises(
        ValueError,
        match="Campos ausentes"
    ):
        extract.validar_resposta_api(resposta)

def test_api_rejeita_listas_de_tamanhos_diferentes():

    resposta = resposta_api_valida()

    resposta["daily"]["precipitation_sum"] = [5.0]

    with pytest.raises(
        ValueError,
        match="quantidades diferentes"
    ):
        extract.validar_resposta_api(resposta)

def test_extracao_usa_localidade_sem_internet(
    monkeypatch
):

    localidade = extract.CIDADES[-1]
    chamadas = []

    class RespostaFalsa:

        def raise_for_status(self):
            pass

        def json(self):
            return resposta_api_valida()

    def get_falso(url, params, timeout):

        chamadas.append({
            "url": url,
            "params": params,
            "timeout": timeout
        })

        return RespostaFalsa()

    monkeypatch.setattr(
        extract.requests,
        "get",
        get_falso
    )

    dados = extract.buscar_dados_climaticos(
        localidade
    )

    assert dados is not None
    assert len(dados) == 2

    assert set(dados["cidade"]) == {
        localidade["cidade"]
    }

    assert set(dados["estado"]) == {
        localidade["estado"]
    }

    assert (
        chamadas[0]["params"]["latitude"]
        == localidade["latitude"]
    )

    assert (
        chamadas[0]["params"]["timezone"]
        == localidade["timezone"]
    )

def test_extracao_retorna_none_quando_api_falha(
    monkeypatch
):

    def get_com_timeout(*args, **kwargs):
        raise requests.exceptions.Timeout(
            "API indisponível"
        )

    monkeypatch.setattr(
        extract.requests,
        "get",
        get_com_timeout
    )

    assert extract.buscar_dados_climaticos(
        extract.CIDADES[0]
    ) is None

# =====================================================
# TESTES DA TRANSFORMAÇÃO
# =====================================================

def test_transformacao_normaliza_cidade_estado_e_data():

    dados = pd.DataFrame([
        registro_valido(
            cidade=" São Paulo ",
            estado=" sp "
        )
    ])

    resultado = transform.validar_tratar_dados(dados)

    assert resultado is not None

    assert resultado.loc[0, "cidade"] == "São Paulo"
    assert resultado.loc[0, "estado"] == "SP"

    assert (
        resultado.loc[0, "data_referencia"]
        == "2026-11-23"
    )

@pytest.mark.parametrize(
    "alteracao",
    [
        {"temperatura_min_c": 35.0},
        {"precipitacao_mm": -2.0},
        {"umidade_media_pct": 105.0},
        {"vento_max_kmh": -1.0},
        {"data_referencia": "data inválida"},
        {"temperatura_max_c": "não numérico"}
    ]
)
def test_transformacao_descarta_registros_invalidos(
    alteracao
):

    dados = pd.DataFrame([
        registro_valido(**alteracao)
    ])

    assert transform.validar_tratar_dados(
        dados
    ) is None

def test_transformacao_mantem_ultima_duplicata():

    dados = pd.DataFrame([
        registro_valido(
            precipitacao_mm=5.0
        ),
        registro_valido(
            precipitacao_mm=18.0
        )
    ])

    resultado = transform.validar_tratar_dados(
        dados
    )

    assert resultado is not None
    assert len(resultado) == 1

    assert (
        resultado.loc[0, "precipitacao_mm"]
        == 18.0
    )

def test_transformacao_recusa_coluna_ausente():

    dados = pd.DataFrame([
        registro_valido()
    ]).drop(
        columns=["cidade"]
    )

    assert transform.validar_tratar_dados(
        dados
    ) is None

# =====================================================
# TESTES DA PREPARAÇÃO PARA MYSQL
# =====================================================

def test_preparacao_mysql_converte_data_e_nulos():

    dados = pd.DataFrame([
        registro_valido(
            vento_max_kmh=float("nan")
        )
    ])

    registros = load.preparar_registros(dados)

    assert len(registros) == 1

    assert (
        registros[0]["data_referencia"].isoformat()
        == "2026-11-23"
    )

    assert registros[0]["vento_max_kmh"] is None

# =====================================================
# SIMULAÇÃO DE CONEXÃO MYSQL
# =====================================================

class ConexaoFalsa:

    def __init__(self, falhar_historico=False):

        self.comandos = []
        self.falhar_historico = falhar_historico

    def execute(self, sql, parametros=None):

        comando = str(sql).strip()

        if (
            self.falhar_historico
            and "INSERT INTO clima_diario_historico"
            in comando
        ):
            raise SQLAlchemyError(
                "Falha simulada no histórico"
            )

        self.comandos.append(
            (comando, parametros)
        )

class MotorFalso:

    def __init__(self, falhar_historico=False):

        self.conexao = ConexaoFalsa(
            falhar_historico
        )

        self.finalizado = False

    def begin(self):
        return nullcontext(
            self.conexao
        )

    def dispose(self):
        self.finalizado = True

# =====================================================
# TESTES DE CARREGAMENTO
# =====================================================

def test_carregamento_grava_previsao_e_historico(
    monkeypatch
):

    motor = MotorFalso()

    monkeypatch.setattr(
        load,
        "criar_conexao",
        lambda: motor
    )

    sucesso = load.salvar_dados_mysql(
        pd.DataFrame([
            registro_valido()
        ])
    )

    comandos = [
        sql
        for sql, _ in motor.conexao.comandos
    ]

    assert sucesso is True

    assert any(
        "CREATE TABLE IF NOT EXISTS "
        "clima_diario_historico" in sql
        for sql in comandos
    )

    assert any(
        "INSERT INTO clima_diario (" in sql
        for sql in comandos
    )

    assert any(
        "INSERT INTO clima_diario_historico" in sql
        for sql in comandos
    )

    assert motor.finalizado is True

def test_carregamento_sinaliza_falha_no_historico(
    monkeypatch
):

    motor = MotorFalso(
        falhar_historico=True
    )

    monkeypatch.setattr(
        load,
        "criar_conexao",
        lambda: motor
    )

    dados = pd.DataFrame([
        registro_valido()
    ])

    assert load.salvar_dados_mysql(
        dados
    ) is False

    assert motor.finalizado is True

# =====================================================
# TESTES DOS ALERTAS METEOROLÓGICOS
# =====================================================

def test_alertas_detectam_atencao_e_nivel_elevado():

    hoje = pd.Timestamp.now(
        tz="America/Sao_Paulo"
    ).date()

    dados = pd.DataFrame([
        registro_valido(
            data_referencia=str(hoje),
            precipitacao_mm=55.0
        ),
        registro_valido(
            cidade="Recife",
            estado="PE",
            data_referencia=str(
                hoje + timedelta(days=1)
            ),
            temperatura_max_c=34.0
        ),
        registro_valido(
            cidade="Curitiba",
            estado="PR",
            data_referencia=str(
                hoje + timedelta(days=1)
            ),
            vento_max_kmh=42.0
        )
    ])

    dados["data_coleta"] = pd.Timestamp(
        "2026-11-23 15:00:00"
    )

    alertas = gerar_alertas(dados)

    assert len(alertas) == 3

    assert (
        alertas["Nível"] == "🔴 Elevado"
    ).sum() == 1

    assert (
        alertas["Nível"] == "🟡 Atenção"
    ).sum() == 2

    assert set(alertas["Cidade"]) == {
        "São Paulo/SP",
        "Recife/PE",
        "Curitiba/PR"
    }

def test_alertas_ignoram_passado_e_ultima_coleta():

    hoje = pd.Timestamp.now(
        tz="America/Sao_Paulo"
    ).date()

    dados = pd.DataFrame([
        registro_valido(
            data_referencia=str(
                hoje - timedelta(days=1)
            ),
            precipitacao_mm=100.0
        ),
        registro_valido(
            data_referencia=str(hoje),
            precipitacao_mm=60.0
        ),
        registro_valido(
            data_referencia=str(hoje),
            precipitacao_mm=2.0
        )
    ])

    dados["data_coleta"] = pd.to_datetime([
        "2026-11-23 09:00:00",
        "2026-11-23 10:00:00",
        "2026-11-23 11:00:00"
    ])

    assert gerar_alertas(dados).empty