# 🌦️ Pipeline de Dados Meteorológicos

Pipeline ETL desenvolvido em Python para coletar previsões meteorológicas da API Open-Meteo, realizar validações e transformações com Pandas e armazenar os dados em um banco de dados MySQL.

O projeto demonstra conceitos fundamentais de Engenharia de Dados, incluindo integração com APIs, tratamento de dados, persistência em banco relacional, prevenção de duplicidades e monitoramento de execuções.

## 🎯 Objetivo

Desenvolver um fluxo automatizado de dados meteorológicos para a cidade de São Paulo, utilizando uma arquitetura ETL (Extract, Transform, Load).

O pipeline coleta previsões para os próximos sete dias, verifica a qualidade das informações e armazena os registros em uma tabela MySQL.

## 🛠️ Tecnologias utilizadas

- **Python:** linguagem principal do projeto.
- **Pandas:** organização, transformação e validação dos dados.
- **Requests:** integração com a API meteorológica.
- **MySQL:** armazenamento dos dados.
- **SQLAlchemy:** gerenciamento da conexão com o banco.
- **PyMySQL:** comunicação entre Python e MySQL.
- **Python-dotenv:** gerenciamento de variáveis de ambiente.
- **Logging:** registro e monitoramento das execuções.

## 🏗️ Arquitetura do projeto

O projeto utiliza uma estrutura modular, separando cada responsabilidade:

```text
pipeline-clima/
│
├── src/
│   ├── __init__.py
│   ├── logging_config.py
│   ├── extract.py
│   ├── transform.py
│   └── load.py
│
├── logs/
│   └── pipeline.log
│
├── main.py
├── requirements.txt
├── .env
└── .gitignore
```

### Fluxo ETL

**1. Extract — Extração**

Coleta de informações meteorológicas por meio da API Open-Meteo.

**2. Transform — Transformação**

Utilização do Pandas para:
- Converter e padronizar os dados.
- Validar datas e valores numéricos.
- Identificar valores ausentes.
- Verificar inconsistências meteorológicas.
- Remover registros inválidos e duplicados.

**3. Load — Carregamento**

Armazenamento dos dados no MySQL utilizando SQLAlchemy e PyMySQL.

O processo utiliza uma chave única por cidade, estado e data para atualizar registros existentes e evitar duplicações.

## 🌐 Fonte dos dados

[Open-Meteo — Weather API](https://open-meteo.com/)

A API fornece informações meteorológicas em formato JSON.

Localidade utilizada:
- Cidade: São Paulo
- Estado: SP
- Latitude: -23.5505
- Longitude: -46.6333

## 📊 Dados coletados

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
- Git instalado (para clonar o repositório).

### 2. Clonar o repositório

```bash
git clone URL_DO_REPOSITORIO
cd pipeline-clima
```

### 3. Criar o ambiente virtual

```bash
python -m venv .venv
```

Ativar no Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 4. Instalar as dependências

```bash
pip install -r requirements.txt
```

### 5. Configurar o banco de dados

Criar o banco:

```sql
CREATE DATABASE projeto_dados;

USE projeto_dados;
```

Criar a tabela:

```sql
CREATE TABLE clima_diario (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cidade VARCHAR(100) NOT NULL,
    estado CHAR(2) NOT NULL,
    data_referencia DATE NOT NULL,
    temperatura_max_c DECIMAL(5,2),
    temperatura_min_c DECIMAL(5,2),
    precipitacao_mm DECIMAL(7,2),
    umidade_media_pct DECIMAL(5,2),
    vento_max_kmh DECIMAL(7,2),
    codigo_clima INT,
    data_coleta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uq_cidade_data (
        cidade,
        estado,
        data_referencia
    )
);
```

### 6. Configurar as variáveis de ambiente

Criar um arquivo `.env` na raiz do projeto:

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=projeto_dados
MYSQL_USER=root
MYSQL_PASSWORD=SUA_SENHA
```

Substitua `SUA_SENHA` pela senha configurada no MySQL.

**Importante:** nunca compartilhe ou publique o arquivo `.env`.

### 7. Executar o pipeline

```bash
python main.py
```

Após a execução, os dados serão coletados, validados e armazenados no banco de dados.

## 📝 Monitoramento

O projeto utiliza o módulo Logging do Python para registrar:

- Início e conclusão da execução.
- Quantidade de registros coletados.
- Resultados da validação.
- Erros durante a comunicação com a API.
- Falhas de conexão ou gravação no MySQL.

Os registros são armazenados em `logs/pipeline.log`, com rotação automática dos arquivos.

## ✅ Resultados alcançados

Durante os testes realizados:

- Extração de sete previsões meteorológicas.
- Validação dos registros com Pandas.
- Identificação de dados inválidos e duplicados.
- Integração entre Python e MySQL.
- Armazenamento e atualização dos registros.
- Teste de execução repetida sem duplicação.
- Organização do código em módulos independentes.
- Implementação de logs para acompanhamento das execuções.

## 🚀 Melhorias futuras

- Automatização periódica da execução do pipeline.
- Inclusão de novas cidades brasileiras.
- Ampliação das análises meteorológicas.
- Implementação de testes automatizados.
- Desenvolvimento de dashboards para visualização dos dados.
- Monitoramento de falhas e qualidade dos dados.

---

**Projeto pessoal desenvolvido para fins de aprendizado e demonstração de conhecimentos em Python, SQL, Pandas e Engenharia de Dados.**