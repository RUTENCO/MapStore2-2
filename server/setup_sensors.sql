-- =============================================================
-- Script: setup_sensors.sql
-- Base de datos: Neon PostgreSQL (neondb)
-- Descripción: Crea las tablas para la red de sensores ambientales
--
-- Ejecutar:
--   psql "postgresql://neondb_owner:...@...neon.tech/neondb?sslmode=require" -f setup_sensors.sql
-- =============================================================

-- ── Extensión para UUIDs (ya incluida en Neon) ────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ═════════════════════════════════════════════════════════════════════
-- 1. TABLA: locations — ubicaciones físicas de los sensores
-- ═════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS locations (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(120) NOT NULL,
    description TEXT,
    latitude    NUMERIC(10, 6),
    longitude   NUMERIC(10, 6),
    altitude_m  NUMERIC(8, 2),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE locations IS 'Ubicaciones geográficas donde están instalados los sensores';

-- ═════════════════════════════════════════════════════════════════════
-- 2. TABLA: sensors — catálogo de sensores
-- ═════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS sensors (
    id            VARCHAR(10)  PRIMARY KEY,          -- Ej: 'S01', 'S02'
    name          VARCHAR(120) NOT NULL,
    description   TEXT,
    unit          VARCHAR(20)  NOT NULL,             -- Ej: '°C', '%', 'hPa'
    color         VARCHAR(7)   NOT NULL DEFAULT '#3b82f6', -- Color hex para gráficas
    location_id   UUID         REFERENCES locations(id) ON DELETE SET NULL,
    active        BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE sensors IS 'Catálogo de sensores registrados en la plataforma';

-- ═════════════════════════════════════════════════════════════════════
-- 3. TABLA: sensor_readings — lecturas de los sensores
-- ═════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS sensor_readings (
    id          BIGSERIAL    PRIMARY KEY,
    sensor_id   VARCHAR(10)  NOT NULL REFERENCES sensors(id) ON DELETE CASCADE,
    value       NUMERIC(12, 4) NOT NULL,
    quality     SMALLINT     DEFAULT 100 CHECK (quality BETWEEN 0 AND 100),
    recorded_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  sensor_readings IS 'Lecturas individuales de cada sensor a lo largo del tiempo';
COMMENT ON COLUMN sensor_readings.quality IS 'Calidad del dato 0-100 (100 = dato confiable)';

-- Índices para consultas por sensor + rango de tiempo (muy frecuentes)
CREATE INDEX IF NOT EXISTS idx_readings_sensor_time
    ON sensor_readings (sensor_id, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_readings_time
    ON sensor_readings (recorded_at DESC);

-- ═════════════════════════════════════════════════════════════════════
-- 4. TABLA: sensor_alerts — alertas generadas por umbrales
-- ═════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS sensor_alerts (
    id          BIGSERIAL   PRIMARY KEY,
    sensor_id   VARCHAR(10) NOT NULL REFERENCES sensors(id) ON DELETE CASCADE,
    level       VARCHAR(10) NOT NULL CHECK (level IN ('info', 'warning', 'critical')),
    message     TEXT        NOT NULL,
    value       NUMERIC(12, 4),
    acknowledged BOOLEAN    NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE sensor_alerts IS 'Alertas generadas cuando un sensor supera umbrales definidos';

-- ═════════════════════════════════════════════════════════════════════
-- 5. DATOS DE PRUEBA — mismos 4 sensores del mockData.js
-- ═════════════════════════════════════════════════════════════════════

-- Ubicación de prueba
INSERT INTO locations (id, name, latitude, longitude, altitude_m)
VALUES (
    'a1b2c3d4-0000-0000-0000-000000000001',
    'Estación Central Bogotá',
    4.7110, -74.0721, 2600
) ON CONFLICT DO NOTHING;

-- Sensores (mismos IDs que mockData.js para migración sin cambios)
INSERT INTO sensors (id, name, unit, color, location_id) VALUES
    ('S01', 'Temperatura Ambiente', '°C',  '#ef4444', 'a1b2c3d4-0000-0000-0000-000000000001'),
    ('S02', 'Humedad Relativa',     '%',   '#3b82f6', 'a1b2c3d4-0000-0000-0000-000000000001'),
    ('S03', 'Presión Atmosférica',  'hPa', '#10b981', 'a1b2c3d4-0000-0000-0000-000000000001'),
    ('S04', 'Velocidad del Viento', 'm/s', '#f59e0b', 'a1b2c3d4-0000-0000-0000-000000000001')
ON CONFLICT (id) DO NOTHING;

-- Lecturas de prueba: 30 días de datos cada 6 horas por sensor
-- (genera ~120 registros por sensor = 480 registros totales)
INSERT INTO sensor_readings (sensor_id, value, recorded_at)
SELECT
    sensor_id,
    ROUND((base + sin(extract(epoch FROM t) / 86400.0) * amp + (random() - 0.5) * amp)::NUMERIC, 2),
    t
FROM (
    SELECT 'S01' AS sensor_id, 22::NUMERIC AS base, 6::NUMERIC  AS amp UNION ALL
    SELECT 'S02',              65::NUMERIC,          15::NUMERIC       UNION ALL
    SELECT 'S03',              1013::NUMERIC,        8::NUMERIC        UNION ALL
    SELECT 'S04',              4::NUMERIC,           3::NUMERIC
) sensors
CROSS JOIN generate_series(
    NOW() - INTERVAL '30 days',
    NOW(),
    INTERVAL '6 hours'
) AS t
ON CONFLICT DO NOTHING;

-- ═════════════════════════════════════════════════════════════════════
-- 6. VISTA útil: últimas lecturas de cada sensor
-- ═════════════════════════════════════════════════════════════════════
CREATE OR REPLACE VIEW latest_readings AS
SELECT DISTINCT ON (r.sensor_id)
    s.id,
    s.name,
    s.unit,
    s.color,
    r.value,
    r.recorded_at,
    r.quality
FROM sensors s
JOIN sensor_readings r ON r.sensor_id = s.id
WHERE s.active = TRUE
ORDER BY r.sensor_id, r.recorded_at DESC;

COMMENT ON VIEW latest_readings IS 'Última lectura de cada sensor activo';

-- ═════════════════════════════════════════════════════════════════════
-- Verificación final
-- ═════════════════════════════════════════════════════════════════════
SELECT
    s.id,
    s.name,
    s.unit,
    COUNT(r.id) AS total_lecturas,
    MIN(r.recorded_at) AS primera_lectura,
    MAX(r.recorded_at) AS ultima_lectura
FROM sensors s
LEFT JOIN sensor_readings r ON r.sensor_id = s.id
GROUP BY s.id, s.name, s.unit
ORDER BY s.id;
