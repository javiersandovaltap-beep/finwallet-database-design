-- ================================================================
-- FINWALLET — Script SQL Completo v2.0
-- Base de datos relacional para sistema de monedero virtual
-- Motor: MySQL 8.0+
-- Autor: Javier Sandoval Tapia
-- ================================================================


-- ================================================================
-- PASO 1: CREAR Y SELECCIONAR LA BASE DE DATOS
-- ================================================================

CREATE DATABASE IF NOT EXISTS FinWallet;
USE FinWallet;


-- ================================================================
-- PASO 2: CREAR TABLAS (DDL)
-- Orden: moneda → usuario → transaccion (respeta integridad referencial)
-- ================================================================

DROP TABLE IF EXISTS transaccion;
DROP TABLE IF EXISTS usuario;
DROP TABLE IF EXISTS moneda;


-- ----------------------------------------------------------------
-- TABLA 1: moneda
-- Catálogo de monedas disponibles en el sistema.
-- ----------------------------------------------------------------
CREATE TABLE moneda (
    currency_id     INT          PRIMARY KEY,
    currency_name   VARCHAR(50)  NOT NULL,
    currency_symbol VARCHAR(10)  NOT NULL,
    CONSTRAINT uq_currency_name   UNIQUE (currency_name),
    CONSTRAINT uq_currency_symbol UNIQUE (currency_symbol)
);

DESCRIBE moneda;


-- ----------------------------------------------------------------
-- TABLA 2: usuario
-- Usuarios registrados en el monedero virtual.
-- Decisiones de diseño:
--   - AUTO_INCREMENT en user_id: unicidad sin asignación manual
--   - DECIMAL(10,2) en saldo: precisión exacta para valores monetarios
--   - UNIQUE en correo_electronico: un correo por cuenta
--   - CHECK saldo >= 0: integridad de negocio a nivel de BD
-- ----------------------------------------------------------------
CREATE TABLE usuario (
    user_id            INT           AUTO_INCREMENT PRIMARY KEY,
    nombre             VARCHAR(100)  NOT NULL,
    correo_electronico VARCHAR(100)  NOT NULL,
    contrasena         VARCHAR(255)  NOT NULL,
    saldo              DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    currency_id        INT           NOT NULL,
    fecha_registro     DATETIME      DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_correo      UNIQUE  (correo_electronico),
    CONSTRAINT fk_usr_moneda  FOREIGN KEY (currency_id) REFERENCES moneda(currency_id),
    CONSTRAINT chk_saldo      CHECK   (saldo >= 0)
);

DESCRIBE usuario;


-- ----------------------------------------------------------------
-- TABLA 3: transaccion
-- Movimientos de dinero entre usuarios.
-- Decisiones de diseño:
--   - Doble FK a usuario: emisor (sender) y receptor (receiver)
--   - DECIMAL(10,2) en importe: consistente con saldo de usuario
--   - CHECK importe > 0: no se permiten transferencias de monto cero
--   - CHECK emisor != receptor: no se puede transferir a uno mismo
--   - DEFAULT CURRENT_TIMESTAMP: fecha/hora automática al insertar
-- ----------------------------------------------------------------
CREATE TABLE transaccion (
    transaction_id   INT           AUTO_INCREMENT PRIMARY KEY,
    sender_user_id   INT           NOT NULL,
    receiver_user_id INT           NOT NULL,
    importe          DECIMAL(10,2) NOT NULL,
    transaction_date DATETIME      DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_trans_sender   FOREIGN KEY (sender_user_id)   REFERENCES usuario(user_id),
    CONSTRAINT fk_trans_receiver FOREIGN KEY (receiver_user_id) REFERENCES usuario(user_id),
    CONSTRAINT chk_importe       CHECK (importe > 0),
    CONSTRAINT chk_no_autotrans  CHECK (sender_user_id != receiver_user_id)
);

DESCRIBE transaccion;


-- ----------------------------------------------------------------
-- ÍNDICES: optimización de búsquedas frecuentes
-- Las consultas por emisor y receptor son las más habituales
-- en un sistema de transferencias. Los índices evitan full scans.
-- ----------------------------------------------------------------
CREATE INDEX idx_trans_sender   ON transaccion(sender_user_id);
CREATE INDEX idx_trans_receiver ON transaccion(receiver_user_id);
CREATE INDEX idx_trans_fecha    ON transaccion(transaction_date);


-- ================================================================
-- PASO 3: INSERTAR DATOS DE PRUEBA (DML)
-- Orden: moneda → usuario → transaccion
-- ================================================================

-- Monedas
INSERT INTO moneda (currency_id, currency_name, currency_symbol) VALUES
    (1, 'Peso Chileno',         'CLP'),
    (2, 'Dolar Estadounidense', 'USD'),
    (3, 'Euro',                 'EUR'),
    (4, 'Peso Argentino',       'ARS');

SELECT * FROM moneda;


-- Usuarios
INSERT INTO usuario (nombre, correo_electronico, contrasena, saldo, currency_id) VALUES
    ('Maria Garcia',   'maria@email.com',   'pass123', 1500.00, 1),
    ('Juan Perez',     'juan@email.com',    'pass456', 2500.00, 2),
    ('Ana Lopez',      'ana@email.com',     'pass789',  800.00, 1),
    ('Carlos Ruiz',    'carlos@email.com',  'pass000', 3000.00, 3),
    ('Valentina Soto', 'vale@email.com',    'pass111', 5000.00, 2);

SELECT * FROM usuario;


-- Transacciones históricas
INSERT INTO transaccion (sender_user_id, receiver_user_id, importe, transaction_date) VALUES
    (1, 2, 200.00, '2024-01-15 10:30:00'),
    (2, 3, 150.00, '2024-01-16 14:45:00'),
    (1, 3, 100.00, '2024-01-17 09:00:00'),
    (4, 1, 500.00, '2024-01-18 16:20:00'),
    (3, 2,  75.00, '2024-01-19 11:15:00'),
    (5, 1, 300.00, '2024-02-01 08:00:00'),
    (2, 5, 250.00, '2024-02-03 17:30:00');

SELECT * FROM transaccion;


-- ================================================================
-- PASO 4: CONSULTAS REQUERIDAS
-- ================================================================

-- 1) Moneda elegida por un usuario específico (JOIN)
SELECT
    u.user_id,
    u.nombre,
    m.currency_name   AS moneda_preferida,
    m.currency_symbol AS simbolo
FROM usuario u
INNER JOIN moneda m ON u.currency_id = m.currency_id
WHERE u.user_id = 1;


-- 2) Todas las transacciones registradas
SELECT * FROM transaccion;


-- 3) Todas las transacciones de un usuario (emisor o receptor)
SELECT *
FROM transaccion
WHERE sender_user_id = 1
   OR receiver_user_id = 1;


-- 4) Modificar el correo electrónico de un usuario (UPDATE)

-- Estado antes del cambio
SELECT user_id, nombre, correo_electronico
FROM usuario WHERE user_id = 1;

UPDATE usuario
SET correo_electronico = 'maria.nuevo@email.com'
WHERE user_id = 1;

-- Verificar el cambio
SELECT user_id, nombre, correo_electronico
FROM usuario WHERE user_id = 1;


-- 5) Eliminar una transacción (DELETE)

-- Estado antes de eliminar
SELECT * FROM transaccion WHERE transaction_id = 5;

DELETE FROM transaccion WHERE transaction_id = 5;

-- Verificar que fue eliminada
SELECT * FROM transaccion WHERE transaction_id = 5;


-- ================================================================
-- PASO 5: TRANSACCIONALIDAD — PROPIEDADES ACID
-- ================================================================

-- ----------------------------------------------------------------
-- CASO 1: Transferencia exitosa con COMMIT
-- Escenario: usuario 1 envía $100 al usuario 2
-- ----------------------------------------------------------------

-- Saldos antes de la transferencia
SELECT user_id, nombre, saldo FROM usuario WHERE user_id IN (1, 2);

START TRANSACTION;

    UPDATE usuario SET saldo = saldo - 100 WHERE user_id = 1;
    UPDATE usuario SET saldo = saldo + 100 WHERE user_id = 2;

    INSERT INTO transaccion (sender_user_id, receiver_user_id, importe)
    VALUES (1, 2, 100.00);

COMMIT;

-- Saldos después — ambos deben reflejar el cambio
SELECT user_id, nombre, saldo FROM usuario WHERE user_id IN (1, 2);

-- Última transacción confirmada
SELECT * FROM transaccion ORDER BY transaction_id DESC LIMIT 1;


-- ----------------------------------------------------------------
-- CASO 2: Transferencia fallida con ROLLBACK
-- Escenario: receptor inexistente (user_id = 999)
-- La FK genera error → ROLLBACK revierte todo
-- ----------------------------------------------------------------

START TRANSACTION;

    INSERT INTO transaccion (sender_user_id, receiver_user_id, importe)
    VALUES (1, 999, 100.00);

ROLLBACK;

-- Verificar que no se insertaron datos incorrectos
SELECT * FROM transaccion ORDER BY transaction_id DESC LIMIT 3;


-- ----------------------------------------------------------------
-- CASO 3: Validación de constraint — intento de auto-transferencia
-- Escenario: usuario intenta enviarse dinero a sí mismo
-- El CHECK constraint lo bloquea a nivel de base de datos
-- ----------------------------------------------------------------

START TRANSACTION;

    INSERT INTO transaccion (sender_user_id, receiver_user_id, importe)
    VALUES (1, 1, 50.00);

ROLLBACK;


-- ================================================================
-- PASO 6: VISTAS (VIEWS) — Consultas reutilizables
-- ================================================================

-- ----------------------------------------------------------------
-- VIEW 1: Detalle completo de transacciones con nombres de usuarios
-- Reemplaza los IDs por nombres legibles para reportes y auditoría
-- ----------------------------------------------------------------
CREATE OR REPLACE VIEW v_transacciones_detalle AS
SELECT
    t.transaction_id,
    s.nombre          AS emisor,
    r.nombre          AS receptor,
    t.importe,
    t.transaction_date,
    m.currency_symbol AS moneda
FROM transaccion t
INNER JOIN usuario s  ON t.sender_user_id   = s.user_id
INNER JOIN usuario r  ON t.receiver_user_id = r.user_id
INNER JOIN moneda  m  ON s.currency_id       = m.currency_id;

-- Usar la vista
SELECT * FROM v_transacciones_detalle;


-- ----------------------------------------------------------------
-- VIEW 2: Resumen de actividad por usuario
-- Útil para un dashboard o panel de estadísticas
-- ----------------------------------------------------------------
CREATE OR REPLACE VIEW v_resumen_usuarios AS
SELECT
    u.user_id,
    u.nombre,
    u.saldo,
    m.currency_symbol                                    AS moneda,
    COUNT(DISTINCT t_out.transaction_id)                 AS total_enviadas,
    COUNT(DISTINCT t_in.transaction_id)                  AS total_recibidas,
    COALESCE(SUM(DISTINCT t_out.importe), 0)             AS monto_total_enviado,
    COALESCE(SUM(DISTINCT t_in.importe),  0)             AS monto_total_recibido
FROM usuario u
INNER JOIN moneda      m     ON u.currency_id         = m.currency_id
LEFT  JOIN transaccion t_out ON u.user_id             = t_out.sender_user_id
LEFT  JOIN transaccion t_in  ON u.user_id             = t_in.receiver_user_id
GROUP BY u.user_id, u.nombre, u.saldo, m.currency_symbol;

-- Usar la vista
SELECT * FROM v_resumen_usuarios;


-- ================================================================
-- CONSULTAS ANALÍTICAS ADICIONALES
-- ================================================================

-- Total enviado y recibido por usuario
SELECT
    u.nombre,
    COALESCE(SUM(t.importe), 0) AS total_enviado
FROM usuario u
LEFT JOIN transaccion t ON u.user_id = t.sender_user_id
GROUP BY u.user_id, u.nombre
ORDER BY total_enviado DESC;


-- Ranking de usuarios por número de transacciones enviadas
SELECT
    u.nombre,
    COUNT(t.transaction_id) AS transacciones_enviadas
FROM usuario u
LEFT JOIN transaccion t ON u.user_id = t.sender_user_id
GROUP BY u.user_id, u.nombre
ORDER BY transacciones_enviadas DESC;


-- Transacciones del último mes
SELECT *
FROM transaccion
WHERE transaction_date >= DATE_SUB(NOW(), INTERVAL 1 MONTH)
ORDER BY transaction_date DESC;
