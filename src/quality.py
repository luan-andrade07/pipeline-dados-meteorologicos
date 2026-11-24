
"""Análise da qualidade das previsões, sem acessar API ou MySQL."""

from datetime import timedelta

import pandas as pd


CAMPOS_OBRIGATORIOS = (
    "cidade",
    "estado",
    "data_referencia",
    "temperatura_max_c",
    "temperatura_min_c",
    "precipitacao_mm",
    "umidade_media_pct",
    "vento_max_kmh",
    "codigo_clima",
    "coleta_utc",
)

COLUNAS_OCORRENCIAS = (
    "Nível",
    "Cidade",
    "Data",
    "Problema",
    "Detalhes"
)


# =====================================================
# VALIDAÇÃO DE UM REGISTRO METEOROLÓGICO
# =====================================================

def verificar_registro(registro):
    """Retorna inconsistências de uma previsão."""

    erros = []
    numericos = {}

    for campo in (
        "temperatura_max_c",
        "temperatura_min_c",
        "precipitacao_mm",
        "umidade_media_pct",
        "vento_max_kmh",
        "codigo_clima"
    ):

        valor = pd.to_numeric(
            registro[campo],
            errors="coerce"
        )

        if (
            pd.isna(valor)
            or not float("-inf") < float(valor) < float("inf")
        ):
            erros.append(
                f"{campo} ausente ou não numérico"
            )
            numericos[campo] = None
        else:
            numericos[campo] = float(valor)

    maxima = numericos["temperatura_max_c"]
    minima = numericos["temperatura_min_c"]
    chuva = numericos["precipitacao_mm"]
    umidade = numericos["umidade_media_pct"]
    vento = numericos["vento_max_kmh"]
    codigo = numericos["codigo_clima"]

    if maxima is not None and not -90 <= maxima <= 60:
        erros.append(
            "temperatura máxima fora de -90 a 60 °C"
        )

    if minima is not None and not -90 <= minima <= 60:
        erros.append(
            "temperatura mínima fora de -90 a 60 °C"
        )

    if (
        maxima is not None
        and minima is not None
        and minima > maxima
    ):
        erros.append(
            "temperatura mínima maior que a máxima"
        )

    if chuva is not None and chuva < 0:
        erros.append("precipitação negativa")

    if umidade is not None and not 0 <= umidade <= 100:
        erros.append("umidade fora de 0 a 100%")

    if vento is not None and vento < 0:
        erros.append("vento negativo")

    if (
        codigo is not None
        and (
            codigo < 0
            or not codigo.is_integer()
        )
    ):
        erros.append("código de clima inválido")

    return erros


# =====================================================
# ANÁLISE GERAL DA QUALIDADE
# =====================================================

def analisar_qualidade(
    df: pd.DataFrame,
    cidades: list[dict],
    *,
    agora=None,
    dias_previsao: int = 7,
    atraso_atencao_h: float = 36,
    atraso_critico_h: float = 72,
):
    """
    Verifica cobertura, consistência e atualização.

    Retorna:
        resumo por cidade
        ocorrências identificadas
    """

    if dias_previsao < 1:
        raise ValueError(
            "dias_previsao deve ser positivo"
        )

    ausentes = (
        set(CAMPOS_OBRIGATORIOS)
        - set(df.columns)
    )

    if ausentes:
        raise ValueError(
            "Colunas necessárias ausentes: "
            f"{sorted(ausentes)}"
        )

    instante = (
        pd.Timestamp.now(tz="UTC")
        if agora is None
        else pd.Timestamp(agora)
    )

    if instante.tzinfo is None:
        raise ValueError(
            "agora deve conter fuso horário"
        )

    instante = instante.tz_convert("UTC")

    hoje = instante.tz_convert(
        "America/Sao_Paulo"
    ).date()

    datas_esperadas = [
        hoje + timedelta(days=i)
        for i in range(dias_previsao)
    ]

    dados = df.copy()

    dados["data_referencia"] = pd.to_datetime(
        dados["data_referencia"],
        errors="coerce"
    ).dt.date

    dados["coleta_utc"] = pd.to_datetime(
        dados["coleta_utc"],
        errors="coerce",
        utc=True
    )

    cidades_resumo = []
    ocorrencias = []

    # =============================================
    # REGISTRO DE OCORRÊNCIAS
    # =============================================

    def registrar(
        nivel,
        cidade,
        estado,
        data,
        problema,
        detalhe
    ):
        ocorrencias.append({
            "Nível": nivel,
            "Cidade": f"{cidade}/{estado}",
            "Data": data,
            "Problema": problema,
            "Detalhes": detalhe,
        })

    # =============================================
    # VERIFICAÇÃO DE CADA CIDADE
    # =============================================

    for localidade in cidades:

        cidade = localidade["cidade"]
        estado = localidade["estado"]

        base = dados[
            dados["cidade"].eq(cidade)
            & dados["estado"].eq(estado)
        ].copy()

        atuais = base[
            base["data_referencia"].isin(
                datas_esperadas
            )
        ].copy()

        presentes = set(
            atuais["data_referencia"].dropna()
        )

        datas_faltantes = [
            data
            for data in datas_esperadas
            if data not in presentes
        ]

        # =========================================
        # DETECTA DATAS SEM PREVISÃO
        # =========================================

        for data in datas_faltantes:

            registrar(
                "CRÍTICO",
                cidade,
                estado,
                data.strftime("%d/%m/%Y"),
                "Previsão ausente",
                "Não há previsão para esta data "
                "na janela atual."
            )

        # =========================================
        # DETECTA REGISTROS INCONSISTENTES
        # =========================================

        invalidos = 0

        for _, registro in atuais.iterrows():

            erros = verificar_registro(
                registro
            )

            if erros:

                invalidos += 1

                registrar(
                    "CRÍTICO",
                    cidade,
                    estado,
                    registro["data_referencia"].strftime(
                        "%d/%m/%Y"
                    ),
                    "Registro inconsistente",
                    "; ".join(erros)
                )

        # =========================================
        # VERIFICA DUPLICIDADES
        # =========================================

        duplicados = int(
            atuais.duplicated(
                subset=["data_referencia"]
            ).sum()
        )

        if duplicados:

            registrar(
                "CRÍTICO",
                cidade,
                estado,
                "—",
                "Datas duplicadas",
                f"{duplicados} registro(s) "
                "repetido(s) para uma mesma data."
            )

        # =========================================
        # VERIFICA ATUALIZAÇÃO DOS DADOS
        # =========================================

        ultima_coleta = base[
            "coleta_utc"
        ].max()

        atraso_h = None

        if pd.isna(ultima_coleta):

            registrar(
                "CRÍTICO",
                cidade,
                estado,
                "—",
                "Sem coleta registrada",
                "A cidade não possui data "
                "de coleta válida."
            )

        else:

            atraso_h = (
                instante - ultima_coleta
            ).total_seconds() / 3600

            if atraso_h > atraso_critico_h:

                registrar(
                    "CRÍTICO",
                    cidade,
                    estado,
                    "—",
                    "Coleta desatualizada",
                    f"Última atualização há "
                    f"{atraso_h:.1f} horas."
                )

            elif atraso_h > atraso_atencao_h:

                registrar(
                    "ATENÇÃO",
                    cidade,
                    estado,
                    "—",
                    "Coleta desatualizada",
                    f"Última atualização há "
                    f"{atraso_h:.1f} horas."
                )

            elif atraso_h < -0.1:

                registrar(
                    "ATENÇÃO",
                    cidade,
                    estado,
                    "—",
                    "Horário da coleta no futuro",
                    "Verifique o relógio e o "
                    "fuso horário da origem."
                )

        # =========================================
        # CLASSIFICAÇÃO FINAL DA CIDADE
        # =========================================

        critico = bool(
            datas_faltantes
            or invalidos
            or duplicados
        )

        critico = (
            critico
            or atraso_h is None
            or atraso_h > atraso_critico_h
        )

        atencao = (
            atraso_h is not None
            and (
                atraso_h > atraso_atencao_h
                or atraso_h < -0.1
            )
        )

        status = (
            "CRÍTICO"
            if critico
            else "ATENÇÃO"
            if atencao
            else "OK"
        )

        cidades_resumo.append({
            "Cidade": cidade,
            "UF": estado,
            "Status": status,
            "Dias presentes": len(presentes),
            "Dias esperados": dias_previsao,
            "Datas ausentes": len(datas_faltantes),
            "Registros inconsistentes": invalidos,
            "Duplicatas": duplicados,
            "Última coleta UTC": ultima_coleta,
            "Atraso (h)": (
                round(atraso_h, 1)
                if atraso_h is not None
                else None
            ),
        })

    resumo = pd.DataFrame(
        cidades_resumo
    )

    detalhes = pd.DataFrame(
        ocorrencias,
        columns=COLUNAS_OCORRENCIAS
    )

    return resumo, detalhes
