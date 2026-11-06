
CREATE DATABASE IF NOT EXISTS projeto_dados
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE projeto_dados;

CREATE TABLE IF NOT EXISTS clima_diario (

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

    CONSTRAINT uq_cidade_data
        UNIQUE (cidade, estado, data_referencia)

) ENGINE=InnoDB;
