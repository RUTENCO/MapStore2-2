/**
 * server/index.js
 * API REST de sensores — conecta con Neon PostgreSQL
 *
 * Endpoints:
 *   GET /api/sensors              → lista de sensores
 *   GET /api/sensors/:id/readings → lecturas filtradas por período
 *   GET /api/health               → health check
 */

require('dotenv').config({ path: '../.env' });

const express = require('express');
const cors    = require('cors');
const { Pool } = require('pg');

const app  = express();
const PORT = process.env.SENSORS_API_PORT || 3001;

// ── Pool de conexiones Neon ───────────────────────────────────────────
const pool = new Pool({
    connectionString: process.env.NEON_DATABASE_URL,
    ssl: { rejectUnauthorized: false }   // requerido por Neon
});

// Verificar conexión al arrancar
pool.connect()
    .then(client => {
        console.log('✅ Conectado a Neon PostgreSQL');
        client.release();
    })
    .catch(err => {
        console.error('❌ Error conectando a Neon:', err.message);
    });

// ── Middlewares ───────────────────────────────────────────────────────
app.use(cors());
app.use(express.json());

// ── Helpers ───────────────────────────────────────────────────────────
const PERIOD_MAP = {
    '24h': '24 hours',
    '7d':  '7 days',
    '30d': '30 days',
    '90d': '90 days'
};

// ── Rutas ─────────────────────────────────────────────────────────────

// Health check
app.get('/api/health', (_req, res) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// GET /api/sensors — lista todos los sensores
app.get('/api/sensors', async (_req, res) => {
    try {
        const { rows } = await pool.query(
            'SELECT * FROM sensors ORDER BY name'
        );
        res.json(rows);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: err.message });
    }
});

// GET /api/sensors/:id/readings?period=7d
// Devuelve lecturas de un sensor en el período solicitado
app.get('/api/sensors/:id/readings', async (req, res) => {
    const { id }     = req.params;
    const period     = req.query.period || '7d';
    const interval   = PERIOD_MAP[period] || '7 days';

    try {
        const { rows } = await pool.query(
            `SELECT
                id,
                sensor_id,
                recorded_at                          AS timestamp,
                TO_CHAR(recorded_at, 'DD/MM HH24:MI') AS label,
                value
             FROM sensor_readings
             WHERE sensor_id = $1
               AND recorded_at >= NOW() - INTERVAL '${interval}'
             ORDER BY recorded_at ASC`,
            [id]
        );
        res.json(rows);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: err.message });
    }
});

// GET /api/sensors/:id/stats?period=7d — estadísticas (min/avg/max)
app.get('/api/sensors/:id/stats', async (req, res) => {
    const { id }   = req.params;
    const period   = req.query.period || '7d';
    const interval = PERIOD_MAP[period] || '7 days';

    try {
        const { rows } = await pool.query(
            `SELECT
                MIN(value)  AS min,
                AVG(value)  AS avg,
                MAX(value)  AS max,
                COUNT(*)    AS total
             FROM sensor_readings
             WHERE sensor_id = $1
               AND recorded_at >= NOW() - INTERVAL '${interval}'`,
            [id]
        );
        res.json(rows[0]);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: err.message });
    }
});

// ── Iniciar servidor ──────────────────────────────────────────────────
app.listen(PORT, () => {
    console.log(`🚀 Sensors API corriendo en http://localhost:${PORT}`);
});
