# 🌦️ Pipeline de Dados Meteorológicos

Projeto de Engenharia de Dados desenvolvido em Python para coletar, transformar, validar e armazenar previsões meteorológicas da cidade de São Paulo. Os dados são disponibilizados em um banco de dados MySQL e apresentados em um dashboard interativo desenvolvido com Streamlit.

O projeto demonstra conceitos de integração com APIs, processamento e qualidade de dados, persistência em banco relacional e visualização de informações.

## 🎯 Objetivo

Construir um pipeline ETL capaz de obter previsões meteorológicas para os próximos sete dias, realizar o tratamento e a validação dos dados e armazená-los em um banco MySQL.

Além do processamento, o projeto disponibiliza um dashboard para consultar indicadores e acompanhar as condições meteorológicas previstas.

## 🛠️ Tecnologias utilizadas

- **Python:** linguagem principal.
- **Pandas:** manipulação e tratamento de dados.
- **NumPy:** operações numéricas e validações.
- **Requests:** integração com a API Open-Meteo.
- **MySQL:** armazenamento dos dados.
- **SQLAlchemy:** gerenciamento da conexão com o banco.
- **PyMySQL:** comunicação com o MySQL.
- **Python-dotenv:** gerenciamento de variáveis de ambiente.
- **Streamlit:** desenvolvimento do dashboard.
- **Plotly:** criação de gráficos interativos.
- **Logging:** registro e monitoramento das execuções.

## 🏗️ Estrutura do projeto

```text
pipeline-clima/
│
├── dashboard/
│   ├── __init__.py
│   ├── app.py
│   ├── components.py
│   └── style.css
│
├── src/
│   ├── __init__.py
│   ├── extract.py
│   ├── transform.py
│   ├── load.py
│   └── logging_config.py
│
├── sql/
│   └── schema.sql
│
├── logs/
│
├── main.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## 🔄 Pipeline ETL

O processamento é dividido em três etapas:

### 1. Extract — Extração

- Consumo da API Open-Meteo.
- Coleta de previsões meteorológicas para São Paulo.
- Recebimento de informações em formato JSON.
- Conversão dos dados para um DataFrame do Pandas.

### 2. Transform — Transformação

- Padronização dos dados.
- Conversão e validação de datas.
- Verificação de valores ausentes e inconsistências.
- Validação de temperaturas, precipitação, umidade e vento.
- Identificação e remoção de registros inválidos.
- Remoção de duplicidades.

### 3. Load — Carregamento

- Conexão com o banco de dados MySQL.
- Preparação dos registros para inserção.
- Persistência dos dados.
- Atualização de registros existentes por meio de uma chave única composta por cidade, estado e data de referência.

## 📊 Dashboard

O projeto conta com um dashboard interativo desenvolvido em Streamlit, com identidade visual escura e componentes organizados para facilitar a análise dos dados.

Principais funcionalidades:

- Filtros por cidade e período.
- Indicadores meteorológicos.
- Destaque da previsão mais próxima.
- Visualização das temperaturas máximas e mínimas.
- Gráficos de precipitação, umidade e velocidade do vento.
- Tabela com os registros meteorológicos e descrição das condições climáticas.

## 🌐 Fonte dos dados

**API utilizada:** [Open-Meteo — Weather API](https://open-meteo.com/)

Localidade de referência:

- Cidade: São Paulo
- Estado: SP
- Latitude: -23.5505
- Longitude: -46.6333

## 📋 Dados armazenados

| Campo | Descrição |
|---|---|
| cidade | Cidade da previsão |
| estado | Unidade federativa |
| data_referencia | Data da previsão |
| temperatura_max_c | Temperatura máxima |
| temperatura_min_c | Temperatura mínima |
| precipitacao_mm | Precipitação acumulada |
| umidade_media_pct | Umidade relativa média |
| vento_max_kmh | Velocidade máxima do vento |
| codigo_clima | Código da condição meteorológica |

## ⚙️ Como executar o projeto

### 1. Pré-requisitos

- Python instalado.
- MySQL Server instalado e em execução.

### 2. Obter o projeto

```bash
git clone https://github.com/luan-andrade07/pipeline-dados-meteorologicos.git
cd pipeline-dados-meteorologicos
```

### 3. Criar e ativar o ambiente virtual

```bash
python -m venv .venv
```

No Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 4. Instalar as dependências

```bash
pip install -r requirements.txt
```

### 5. Configurar o banco de dados

Crie o banco de dados MySQL:

```sql
CREATE DATABASE projeto_dados;
```

Execute o script `sql/schema.sql` para criar a estrutura da tabela.

### 6. Configurar as variáveis de ambiente

Crie uma cópia do arquivo `.env.example` com o nome `.env` e configure os dados da sua conexão MySQL:

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=projeto_dados
MYSQL_USER=root
MYSQL_PASSWORD=SUA_SENHA
```

Substitua `SUA_SENHA` pela senha configurada no seu MySQL.

**Importante:** o arquivo `.env` contém informações sensíveis e não deve ser enviado ao GitHub.

### 7. Executar o pipeline

Na raiz do projeto:

```bash
python main.py
```

### 8. Executar o dashboard

Na raiz do projeto:

```bash
python -m streamlit run dashboard/app.py
```

O Streamlit disponibilizará o dashboard no navegador.

## 📝 Monitoramento

O projeto utiliza o módulo Logging do Python para registrar:

- Início e conclusão das execuções.
- Quantidade de registros coletados.
- Resultados das validações.
- Erros na comunicação com a API.
- Falhas de conexão e gravação no banco.

Os registros são armazenados em `logs/pipeline.log`, com rotação automática dos arquivos.

## ✅ Resultados e funcionalidades implementadas

- Pipeline ETL modularizado em Python.
- Integração com API externa.
- Tratamento e validação de dados com Pandas e NumPy.
- Armazenamento em banco de dados relacional.
- Prevenção de duplicidades e atualização de registros.
- Registro de eventos e erros com Logging.
- Dashboard interativo com Streamlit e Plotly.
- Indicadores e gráficos para análise meteorológica.

## 🚀 Possíveis evoluções

- Inclusão de novas cidades brasileiras.
- Automatização periódica da coleta.
- Ampliação dos indicadores meteorológicos.
- Disponibilização do dashboard em ambiente online.
- Monitoramento automatizado da qualidade dos dados.

---

**Projeto pessoal desenvolvido para fins de aprendizado e demonstração de conhecimentos em Python, SQL, tratamento de dados e Engenharia de Dados.**