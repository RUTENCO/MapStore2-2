/**
 * server/index.js
 * API REST de sensores — conecta con Firebase Realtime Database
 *
 * Endpoints:
 *   GET /api/sensors                       → lista de sensores
 *   GET /api/sensors/:id/readings          → historico de un sensor
 *   GET /api/sensors/:id/latest            → ultimo valor
 *   GET /api/sensors/:id/stats             → min/avg/max
 *   GET /api/sensors/:id/average           → promedio por intervalo
 *   GET /api/sensors/:id/accumulated       → acumulado
 *   GET /api/sensors/:id/peaks             → picos por umbral
 *   GET /api/sensors/:id/histogram         → histograma
 *   GET /api/sensors/:id/stream            → streaming SSE
 *   GET /api/stations/:stationId/compare   → comparacion multi-linea por sensores
 *   GET /api/stations/:stationId/latest    → ultimos valores de multiples sensores
 *   GET /api/zones/:zoneId/stations/compare→ comparacion entre estaciones
 *   GET /api/zones/:zoneId/aggregate       → agregacion por zona
 */

require('dotenv').config({ path: '../.env' });

const fs = require('fs');
const path = require('path');
const express = require('express');
const cors    = require('cors');
const admin = require('firebase-admin');

const app  = express();
const PORT = process.env.SENSORS_API_PORT || 3001;

const FIREBASE_DATABASE_URL = process.env.FIREBASE_DATABASE_URL
    || 'https://estacion-alertas-tempranas-default-rtdb.firebaseio.com';
const FIREBASE_SERVICE_ACCOUNT_PATH = process.env.FIREBASE_SERVICE_ACCOUNT_PATH
    || path.resolve(__dirname, '../estacion-alertas-tempranas-firebase-adminsdk-fbsvc-0bb37ba309.json');
const DEFAULT_ZONE = process.env.FIREBASE_DEFAULT_ZONE || 'Z1';
const DEFAULT_STATION = process.env.FIREBASE_DEFAULT_STATION || 'E1';

const SENSOR_CATALOG = {
    T1: { id: 'T1', name: 'Temperatura Suelo 1', unit: '°C', color: '#ef4444' },
    H1: { id: 'H1', name: 'Humedad Suelo 1', unit: '%', color: '#3b82f6' },
    T2: { id: 'T2', name: 'Temperatura Suelo 2', unit: '°C', color: '#f97316' },
    H2: { id: 'H2', name: 'Humedad Suelo 2', unit: '%', color: '#6366f1' },
    T3: { id: 'T3', name: 'Temperatura Suelo 3', unit: '°C', color: '#dc2626' },
    H3: { id: 'H3', name: 'Humedad Suelo 3', unit: '%', color: '#2563eb' },
    T4: { id: 'T4', name: 'Temperatura Aire', unit: '°C', color: '#f59e0b' },
    H4: { id: 'H4', name: 'Humedad Aire', unit: '%', color: '#14b8a6' },
    W1: { id: 'W1', name: 'Velocidad Viento', unit: 'm/s', color: '#8b5cf6' },
    R1: { id: 'R1', name: 'Lluvia', unit: 'mm', color: '#0ea5e9' }
};

const ZONES_FALLBACK = [
    { id: 'Z1', name: 'Zona 1' },
    { id: 'Z2', name: 'Zona 2' },
    { id: 'Z3', name: 'Zona 3' },
    { id: 'Z4', name: 'Zona 4' }
];

const STATIONS_FALLBACK = [
    { id: 'E1', name: 'Estación 01' },
    { id: 'E2', name: 'Estación 02' },
    { id: 'E3', name: 'Estación 03' }
];

const orderingMetaCache = new Map();

function loadServiceAccount() {
    if (!fs.existsSync(FIREBASE_SERVICE_ACCOUNT_PATH)) {
        throw new Error(`No se encontro la clave de Firebase en: ${FIREBASE_SERVICE_ACCOUNT_PATH}`);
    }
    return JSON.parse(fs.readFileSync(FIREBASE_SERVICE_ACCOUNT_PATH, 'utf8'));
}

try {
    if (!admin.apps.length) {
        admin.initializeApp({
            credential: admin.credential.cert(loadServiceAccount()),
            databaseURL: FIREBASE_DATABASE_URL
        });
    }
    console.log('✅ Conectado a Firebase Realtime Database');
} catch (err) {
    console.error('❌ Error inicializando Firebase:', err.message);
}

const db = admin.database();

// ── Middlewares ───────────────────────────────────────────────────────
app.use(cors());
app.use(express.json());

// ── Helpers ───────────────────────────────────────────────────────────
const PERIOD_MAP_MS = {
    '24h': 24 * 60 * 60 * 1000,
    '7d': 7 * 24 * 60 * 60 * 1000,
    '30d': 30 * 24 * 60 * 60 * 1000,
    '90d': 90 * 24 * 60 * 60 * 1000
};

function getZoneAndStation(req) {
    return {
        zoneId: req.query.zone || DEFAULT_ZONE,
        stationId: req.query.station || DEFAULT_STATION
    };
}

function getSensorReadingsRef(zoneId, stationId, sensorId) {
    return db.ref(`zones/${zoneId}/stations/${stationId}/sensors/${sensorId}/readings`);
}

function getRangeFromRequest(req) {
    const now = Date.now();
    const period = req.query.period || '7d';
    const periodMs = PERIOD_MAP_MS[period] || PERIOD_MAP_MS['7d'];
    const parsedStart = req.query.start !== undefined ? Number(req.query.start) : null;
    const parsedEnd = req.query.end !== undefined ? Number(req.query.end) : null;
    const startMs = Number.isFinite(parsedStart) ? parsedStart : (now - periodMs);
    const endMs = Number.isFinite(parsedEnd) ? parsedEnd : now;
    return { period, startMs, endMs };
}

function isFirebaseInvalidQueryError(error) {
    const code = String(error?.code || '').toUpperCase();
    const message = String(error?.message || '').toLowerCase();
    return code.includes('INVALID_PARAMETERS')
        || code.includes('INVALID_QUERY')
        || message.includes('invalid_parameters')
        || message.includes('invalid query parameter');
}

function toEpochMs(value) {
    if (value instanceof Date) return value.getTime();
    if (typeof value === 'number') return value;
    if (typeof value === 'string') {
        const asNumber = Number(value);
        if (!Number.isNaN(asNumber) && asNumber > 0) return asNumber;
        const asDate = Date.parse(value);
        if (!Number.isNaN(asDate)) return asDate;
    }
    return null;
}

function normalizeReading(key, node) {
    if (node == null) return null;

    if (typeof node === 'number') {
        const timestamp = toEpochMs(key);
        if (!timestamp) return null;
        return { id: key, timestamp, value: node };
    }

    if (typeof node !== 'object') return null;

    const timestamp = toEpochMs(node.timestamp)
        || toEpochMs(node.ts)
        || toEpochMs(node.time)
        || toEpochMs(node.fecha)
        || toEpochMs(node.datetime)
        || toEpochMs(node.recorded_at)
        || toEpochMs(node.createdAt)
        || toEpochMs(node.created_at)
        || toEpochMs(key);

    const rawValue = node.value
        ?? node.val
        ?? node.reading
        ?? node.valor
        ?? node.measure
        ?? node.measurement;

    const scalarValue = (rawValue && typeof rawValue === 'object')
        ? (rawValue.value ?? rawValue.val ?? rawValue.reading)
        : rawValue;

    const value = Number(scalarValue);

    if (!timestamp || Number.isNaN(value)) return null;

    return {
        id: key,
        timestamp,
        value
    };
}

function formatLabel(timestamp) {
    const date = new Date(timestamp);
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const hour = String(date.getHours()).padStart(2, '0');
    const minute = String(date.getMinutes()).padStart(2, '0');
    return `${day}/${month} ${hour}:${minute}`;
}

function mapReadings(snapshotVal) {
    const data = snapshotVal || {};
    return Object.entries(data)
        .map(([key, node]) => normalizeReading(key, node))
        .filter(Boolean)
        .sort((a, b) => a.timestamp - b.timestamp)
        .map(r => ({
            id: r.id,
            timestamp: new Date(r.timestamp).toISOString(),
            label: formatLabel(r.timestamp),
            value: r.value
        }));
}

function detectTimestampField(node) {
    if (!node || typeof node !== 'object') return null;
    const candidates = [
        'timestamp',
        'ts',
        'time',
        'fecha',
        'datetime',
        'recorded_at',
        'createdAt',
        'created_at'
    ];
    return candidates.find(field => node[field] !== undefined) || null;
}

async function getOrderingMeta(ref) {
    const cacheKey = ref.toString();
    if (orderingMetaCache.has(cacheKey)) {
        return orderingMetaCache.get(cacheKey);
    }

    const snap = await ref.limitToFirst(1).once('value');
    const firstEntry = Object.entries(snap.val() || {})[0];

    if (!firstEntry) {
        const meta = { mode: 'key', field: null };
        orderingMetaCache.set(cacheKey, meta);
        return meta;
    }

    const [firstKey, firstNode] = firstEntry;
    const field = detectTimestampField(firstNode);
    const meta = field
        ? { mode: 'child', field }
        : (toEpochMs(firstKey) ? { mode: 'key', field: null } : { mode: 'child', field: 'timestamp' });

    orderingMetaCache.set(cacheKey, meta);
    return meta;
}

async function queryByKeyRange(ref, startMs, endMs) {
    try {
        let snap = await ref
            .orderByKey()
            .startAt(String(startMs))
            .endAt(String(endMs))
            .once('value');

        let rows = mapReadings(snap.val());
        if (rows.length) return rows;

        snap = await ref
            .orderByKey()
            .startAt(new Date(startMs).toISOString())
            .endAt(new Date(endMs).toISOString())
            .once('value');

        rows = mapReadings(snap.val());
        if (rows.length) return rows;
    } catch (error) {
        if (!isFirebaseInvalidQueryError(error)) {
            throw error;
        }
    }

    const fallbackSnap = await ref.limitToLast(20000).once('value');
    const fallbackRows = mapReadings(fallbackSnap.val());
    return fallbackRows.filter(r => {
        const ts = Date.parse(r.timestamp);
        return ts >= startMs && ts <= endMs;
    });
}

async function queryByChildRange(ref, field, startMs, endMs) {
    try {
        let snap = await ref
            .orderByChild(field)
            .startAt(startMs)
            .endAt(endMs)
            .once('value');

        let rows = mapReadings(snap.val());
        if (rows.length) return rows;

        snap = await ref
            .orderByChild(field)
            .startAt(new Date(startMs).toISOString())
            .endAt(new Date(endMs).toISOString())
            .once('value');

        rows = mapReadings(snap.val());
        if (rows.length) return rows;
    } catch (error) {
        if (!isFirebaseInvalidQueryError(error)) {
            throw error;
        }
        return queryByKeyRange(ref, startMs, endMs);
    }

    const fallbackSnap = await ref.limitToLast(20000).once('value');
    const fallbackRows = mapReadings(fallbackSnap.val());
    return fallbackRows.filter(r => {
        const ts = Date.parse(r.timestamp);
        return ts >= startMs && ts <= endMs;
    });
}

async function queryReadingsByRange(ref, startMs, endMs) {
    const orderingMeta = await getOrderingMeta(ref);
    if (orderingMeta.mode === 'key') {
        return queryByKeyRange(ref, startMs, endMs);
    }
    return queryByChildRange(ref, orderingMeta.field, startMs, endMs);
}

async function queryLatestReadings(ref, limit = 1) {
    const safeLimit = Math.max(1, Math.min(Number(limit) || 1, 2000));
    const orderingMeta = await getOrderingMeta(ref);

    let snap;
    try {
        if (orderingMeta.mode === 'key') {
            snap = await ref.orderByKey().limitToLast(safeLimit).once('value');
        } else {
            snap = await ref.orderByChild(orderingMeta.field).limitToLast(safeLimit).once('value');
        }
    } catch (error) {
        if (!isFirebaseInvalidQueryError(error)) {
            throw error;
        }
        snap = await ref.limitToLast(Math.max(100, safeLimit * 20)).once('value');
    }

    let rows = mapReadings(snap.val());
    if (!rows.length) {
        snap = await ref.limitToLast(Math.max(100, safeLimit * 20)).once('value');
        rows = mapReadings(snap.val());
    }
    return rows.slice(-safeLimit);
}

function isDateKey(key) {
    return /^\d{4}-\d{2}-\d{2}$/.test(String(key));
}

function parseBucketTimestamp(dayKey, timeKey) {
    const normalizedTime = String(timeKey).replace(/-/g, ':');
    const timestamp = Date.parse(`${dayKey}T${normalizedTime}`);
    return Number.isNaN(timestamp) ? null : timestamp;
}

function mapBucketedStationRows(stationNode, sensorId, startMs, endMs) {
    if (!stationNode || typeof stationNode !== 'object') return [];

    const rows = [];
    Object.keys(stationNode)
        .filter(dayKey => isDateKey(dayKey))
        .forEach(dayKey => {
            const dayNode = stationNode[dayKey];
            if (!dayNode || typeof dayNode !== 'object') return;

            Object.keys(dayNode).forEach(timeKey => {
                const bucketNode = dayNode[timeKey];
                if (!bucketNode || typeof bucketNode !== 'object') return;

                const timestamp = parseBucketTimestamp(dayKey, timeKey);
                if (!timestamp || timestamp < startMs || timestamp > endMs) return;

                const value = Number(bucketNode[sensorId]);
                if (Number.isNaN(value)) return;

                rows.push({
                    id: `${dayKey}-${timeKey}`,
                    timestamp: new Date(timestamp).toISOString(),
                    label: formatLabel(timestamp),
                    value
                });
            });
        });

    return rows.sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));
}

function extractSensorIdsFromBucketedStationNode(stationNode) {
    if (!stationNode || typeof stationNode !== 'object') return [];

    const dayKeys = Object.keys(stationNode).filter(isDateKey).sort();
    for (const dayKey of dayKeys) {
        const dayNode = stationNode[dayKey];
        if (!dayNode || typeof dayNode !== 'object') continue;

        const timeKeys = Object.keys(dayNode).sort();
        for (const timeKey of timeKeys) {
            const rowNode = dayNode[timeKey];
            if (!rowNode || typeof rowNode !== 'object') continue;
            return Object.keys(rowNode).sort();
        }
    }

    return [];
}

async function getBucketedStationNode(zoneId, stationId) {
    const candidatePaths = [
        `zonas/${zoneId}/${stationId}`,
        `zones/${zoneId}/stations/${stationId}`
    ];

    for (const candidatePath of candidatePaths) {
        const snap = await db.ref(candidatePath).once('value');
        const node = snap.val();
        if (node && typeof node === 'object' && Object.keys(node).some(isDateKey)) {
            return node;
        }
    }

    return null;
}

async function queryBucketedReadingsByRange(zoneId, stationId, sensorId, startMs, endMs) {
    const stationNode = await getBucketedStationNode(zoneId, stationId);
    if (!stationNode) return [];
    return mapBucketedStationRows(stationNode, sensorId, startMs, endMs);
}

async function querySensorReadings(zoneId, stationId, sensorId, startMs, endMs) {
    const bucketRows = await queryBucketedReadingsByRange(zoneId, stationId, sensorId, startMs, endMs);
    if (bucketRows.length) {
        return bucketRows;
    }

    const ref = getSensorReadingsRef(zoneId, stationId, sensorId);

    try {
        const rows = await queryReadingsByRange(ref, startMs, endMs);
        if (rows.length) return rows;
    } catch (error) {
        if (!isFirebaseInvalidQueryError(error)) {
            console.error(error);
        }
    }

    return queryBucketedReadingsByRange(zoneId, stationId, sensorId, startMs, endMs);
}

async function querySensorLatest(zoneId, stationId, sensorId, limit = 1) {
    const safeLimit = Math.max(1, Math.min(Number(limit) || 1, 2000));

    const endMs = Date.now();
    const startMs = endMs - PERIOD_MAP_MS['90d'];
    const bucketRows = await queryBucketedReadingsByRange(zoneId, stationId, sensorId, startMs, endMs);
    if (bucketRows.length) {
        return bucketRows.slice(-safeLimit);
    }

    const ref = getSensorReadingsRef(zoneId, stationId, sensorId);

    try {
        const rows = await queryLatestReadings(ref, safeLimit);
        if (rows.length) return rows;
    } catch (error) {
        if (!isFirebaseInvalidQueryError(error)) {
            console.error(error);
        }
    }

    return [];
}

function aggregateByInterval(rows, interval = 'hour') {
    const bucketMs = {
        minute: 60 * 1000,
        hour: 60 * 60 * 1000,
        day: 24 * 60 * 60 * 1000
    }[interval] || 60 * 60 * 1000;

    const buckets = new Map();
    rows.forEach(r => {
        const ts = Date.parse(r.timestamp);
        const bucket = Math.floor(ts / bucketMs) * bucketMs;
        const current = buckets.get(bucket) || { sum: 0, count: 0 };
        current.sum += Number(r.value);
        current.count += 1;
        buckets.set(bucket, current);
    });

    return [...buckets.entries()]
        .sort((a, b) => a[0] - b[0])
        .map(([bucket, acc]) => ({
            timestamp: new Date(bucket).toISOString(),
            label: formatLabel(bucket),
            avg: Number((acc.sum / acc.count).toFixed(3)),
            count: acc.count
        }));
}

function summarizeStats(rows) {
    if (!rows.length) return { min: null, avg: null, max: null, total: 0 };
    const values = rows.map(r => Number(r.value));
    const min = Math.min(...values);
    const max = Math.max(...values);
    const avg = values.reduce((a, b) => a + b, 0) / values.length;
    return {
        min: Number(min.toFixed(3)),
        avg: Number(avg.toFixed(3)),
        max: Number(max.toFixed(3)),
        total: rows.length
    };
}

function buildHistogram(rows, bins = 10) {
    if (!rows.length) return [];
    const values = rows.map(r => Number(r.value)).filter(v => !Number.isNaN(v));
    const min = Math.min(...values);
    const max = Math.max(...values);

    if (min === max) {
        return [{ from: min, to: max, count: values.length }];
    }

    const step = (max - min) / bins;
    const histogram = Array.from({ length: bins }, (_, i) => ({
        from: Number((min + i * step).toFixed(3)),
        to: Number((min + (i + 1) * step).toFixed(3)),
        count: 0
    }));

    values.forEach(v => {
        const idx = Math.min(Math.floor((v - min) / step), bins - 1);
        histogram[idx].count += 1;
    });

    return histogram;
}

// ── Rutas ─────────────────────────────────────────────────────────────

// Health check
app.get('/api/health', (_req, res) => {
    res.json({
        status: 'ok',
        timestamp: new Date().toISOString(),
        provider: 'firebase-realtime-database',
        defaultZone: DEFAULT_ZONE,
        defaultStation: DEFAULT_STATION
    });
});

// Zonas disponibles para el filtro de frontend
app.get('/api/zones', async (_req, res) => {
    try {
        const zonesSnap = await db.ref('zones').once('value');
        const zonesNode = zonesSnap.val() || {};
        let zoneIds = Object.keys(zonesNode).sort();

        if (!zoneIds.length) {
            const zonasSnap = await db.ref('zonas').once('value');
            const zonasNode = zonasSnap.val() || {};
            zoneIds = Object.keys(zonasNode).sort();
        }

        if (!zoneIds.length) {
            return res.json(ZONES_FALLBACK);
        }

        const zones = zoneIds.map(zoneId => ({
            id: zoneId,
            name: zonesNode[zoneId]?.name || `Zona ${zoneId.replace(/^Z/i, '')}`
        }));

        res.json(zones);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: err.message });
    }
});

// Estaciones por zona para el filtro de frontend
app.get('/api/zones/:zoneId/stations', async (req, res) => {
    try {
        const { zoneId } = req.params;
        const stationsSnap = await db.ref(`zones/${zoneId}/stations`).once('value');
        const stationsNode = stationsSnap.val() || {};
        let stationIds = Object.keys(stationsNode).sort();

        if (!stationIds.length) {
            const estacionesSnap = await db.ref(`zonas/${zoneId}`).once('value');
            const estacionesNode = estacionesSnap.val() || {};
            stationIds = Object.keys(estacionesNode).sort();
        }

        if (!stationIds.length) {
            return res.json(STATIONS_FALLBACK);
        }

        const stations = stationIds.map(stationId => ({
            id: stationId,
            name: stationsNode[stationId]?.name || `Estación ${stationId.replace(/^E/i, '')}`
        }));

        res.json(stations);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: err.message });
    }
});

// GET /api/sensors?zone=Z1&station=E1
app.get('/api/sensors', async (req, res) => {
    try {
        const { zoneId, stationId } = getZoneAndStation(req);
        const sensorsRef = db.ref(`zones/${zoneId}/stations/${stationId}/sensors`);
        const snap = await sensorsRef.once('value');
        const node = snap.val() || {};

        const sensorIds = Object.keys(node)
            .filter(id => id !== 'meta' && id !== 'metadata')
            .sort();

        let finalSensorIds = sensorIds;
        if (!finalSensorIds.length) {
            const stationNode = await getBucketedStationNode(zoneId, stationId);
            const bucketSensorIds = extractSensorIdsFromBucketedStationNode(stationNode);
            finalSensorIds = bucketSensorIds.length ? bucketSensorIds : Object.keys(SENSOR_CATALOG);
        }

        const sensors = finalSensorIds.map(id => {
            const meta = SENSOR_CATALOG[id] || {};
            return {
                id,
                name: meta.name || `Sensor ${id}`,
                unit: meta.unit || (node[id] && node[id].unit) || '',
                color: meta.color || '#0C5ECA'
            };
        });

        res.json(sensors);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: err.message });
    }
});

// 1) Historico de un sensor (linea)
app.get('/api/sensors/:id/readings', async (req, res) => {
    try {
        const { id } = req.params;
        const { zoneId, stationId } = getZoneAndStation(req);
        const { startMs, endMs } = getRangeFromRequest(req);
        const rows = await querySensorReadings(zoneId, stationId, id, startMs, endMs);
        res.json(rows);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: err.message });
    }
});

// 2) Ultimo valor de un sensor
app.get('/api/sensors/:id/latest', async (req, res) => {
    try {
        const { id } = req.params;
        const { zoneId, stationId } = getZoneAndStation(req);
        const rows = await querySensorLatest(zoneId, stationId, id, 1);
        res.json(rows[0] || null);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: err.message });
    }
});

// 3) Ultimos N valores de un sensor
app.get('/api/sensors/:id/latest/:n', async (req, res) => {
    try {
        const { id, n } = req.params;
        const limit = Math.max(1, Math.min(Number(n) || 50, 2000));
        const { zoneId, stationId } = getZoneAndStation(req);
        const rows = await querySensorLatest(zoneId, stationId, id, limit);
        res.json(rows);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: err.message });
    }
});

// Estadisticas min/avg/max (util para cards)
app.get('/api/sensors/:id/stats', async (req, res) => {
    try {
        const { id } = req.params;
        const { zoneId, stationId } = getZoneAndStation(req);
        const { startMs, endMs } = getRangeFromRequest(req);
        const rows = await querySensorReadings(zoneId, stationId, id, startMs, endMs);
        res.json(summarizeStats(rows));
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: err.message });
    }
});

// 4) Comparacion entre sensores (multi-linea en una estacion)
app.get('/api/stations/:stationId/compare', async (req, res) => {
    try {
        const zoneId = req.query.zone || DEFAULT_ZONE;
        const stationId = req.params.stationId;
        const sensors = String(req.query.sensors || 'T1,H1,T4')
            .split(',')
            .map(s => s.trim())
            .filter(Boolean);
        const { startMs, endMs } = getRangeFromRequest(req);

        const series = await Promise.all(sensors.map(async sensorId => {
            const rows = await querySensorReadings(zoneId, stationId, sensorId, startMs, endMs);
            return { sensorId, rows };
        }));

        res.json({ zoneId, stationId, startMs, endMs, series });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: err.message });
    }
});

// 5) Promedio por intervalo de tiempo
app.get('/api/sensors/:id/average', async (req, res) => {
    try {
        const { id } = req.params;
        const { zoneId, stationId } = getZoneAndStation(req);
        const { startMs, endMs } = getRangeFromRequest(req);
        const interval = req.query.interval || 'hour'; // minute|hour|day
        const rows = await querySensorReadings(zoneId, stationId, id, startMs, endMs);
        const averages = aggregateByInterval(rows, interval);
        res.json({ sensorId: id, interval, total: averages.length, rows: averages });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: err.message });
    }
});

// 6) Comparacion entre estaciones (misma zona, mismo sensor)
app.get('/api/zones/:zoneId/stations/compare', async (req, res) => {
    try {
        const { zoneId } = req.params;
        const sensorId = req.query.sensorId || 'T4';
        const stations = String(req.query.stations || 'E1,E2,E3')
            .split(',')
            .map(s => s.trim())
            .filter(Boolean);
        const { startMs, endMs } = getRangeFromRequest(req);

        const series = await Promise.all(stations.map(async stationId => {
            const rows = await querySensorReadings(zoneId, stationId, sensorId, startMs, endMs);
            return { stationId, rows };
        }));

        res.json({ zoneId, sensorId, stations, startMs, endMs, series });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: err.message });
    }
});

// 7) Datos acumulados (ej: lluvia)
app.get('/api/sensors/:id/accumulated', async (req, res) => {
    try {
        const { id } = req.params;
        const { zoneId, stationId } = getZoneAndStation(req);
        const { startMs, endMs } = getRangeFromRequest(req);
        const rows = await querySensorReadings(zoneId, stationId, id, startMs, endMs);
        const total = rows.reduce((acc, r) => acc + Number(r.value), 0);
        res.json({ sensorId: id, total: Number(total.toFixed(3)), count: rows.length, rows });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: err.message });
    }
});

// 8) Deteccion de valores extremos por umbral
app.get('/api/sensors/:id/peaks', async (req, res) => {
    try {
        const { id } = req.params;
        const threshold = Number(req.query.threshold);
        if (Number.isNaN(threshold)) {
            return res.status(400).json({ error: 'El parametro threshold es obligatorio y numerico' });
        }

        const { zoneId, stationId } = getZoneAndStation(req);
        const { startMs, endMs } = getRangeFromRequest(req);
        const rows = await querySensorReadings(zoneId, stationId, id, startMs, endMs);
        const peaks = rows.filter(r => Number(r.value) > threshold);
        res.json({ sensorId: id, threshold, total: peaks.length, rows: peaks });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: err.message });
    }
});

// 9) Datos por zona (agregacion geografica)
app.get('/api/zones/:zoneId/aggregate', async (req, res) => {
    try {
        const { zoneId } = req.params;
        const sensorId = req.query.sensorId || 'T4';
        const stationsNode = await db.ref(`zones/${zoneId}/stations`).once('value');
        const stations = Object.keys(stationsNode.val() || {});
        const { startMs, endMs } = getRangeFromRequest(req);

        const byStation = await Promise.all(stations.map(async stationId => {
            const rows = await querySensorReadings(zoneId, stationId, sensorId, startMs, endMs);
            return {
                stationId,
                stats: summarizeStats(rows)
            };
        }));

        res.json({ zoneId, sensorId, startMs, endMs, byStation });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: err.message });
    }
});

// 10) Distribucion de valores (histograma)
app.get('/api/sensors/:id/histogram', async (req, res) => {
    try {
        const { id } = req.params;
        const bins = Math.max(2, Math.min(Number(req.query.bins) || 10, 100));
        const { zoneId, stationId } = getZoneAndStation(req);
        const { startMs, endMs } = getRangeFromRequest(req);
        const rows = await querySensorReadings(zoneId, stationId, id, startMs, endMs);
        const histogram = buildHistogram(rows, bins);
        res.json({ sensorId: id, bins, histogram });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: err.message });
    }
});

// 11) Streaming en tiempo real (SSE)
app.get('/api/sensors/:id/stream', async (req, res) => {
    const { id } = req.params;
    const { zoneId, stationId } = getZoneAndStation(req);

    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    res.flushHeaders();

    let lastPayloadId = null;

    const pushLatest = async () => {
        try {
            const rows = await querySensorLatest(zoneId, stationId, id, 1);
            const payload = rows.length ? rows[0] : null;
            const payloadId = payload ? `${payload.id}-${payload.timestamp}-${payload.value}` : 'null';

            if (payloadId !== lastPayloadId) {
                lastPayloadId = payloadId;
                res.write(`data: ${JSON.stringify(payload)}\n\n`);
            }
        } catch (error) {
            res.write(`event: error\ndata: ${JSON.stringify({ error: error.message })}\n\n`);
        }
    };

    // Primer push inmediato + sondeo cada 5s
    pushLatest();
    const intervalId = setInterval(pushLatest, 5000);

    req.on('close', () => {
        clearInterval(intervalId);
        res.end();
    });
});

// 12) Ultimos valores de multiples sensores
app.get('/api/stations/:stationId/latest', async (req, res) => {
    try {
        const zoneId = req.query.zone || DEFAULT_ZONE;
        const stationId = req.params.stationId;
        const sensors = String(req.query.sensors || 'T1,H1,T4,H4,W1,R1')
            .split(',')
            .map(s => s.trim())
            .filter(Boolean);

        const latestValues = await Promise.all(sensors.map(async sensorId => {
            const rows = await querySensorLatest(zoneId, stationId, sensorId, 1);
            return {
                sensorId,
                latest: rows[0] || null
            };
        }));

        res.json({ zoneId, stationId, latestValues });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: err.message });
    }
});

// ── Iniciar servidor ──────────────────────────────────────────────────
app.listen(PORT, () => {
    console.log(`🚀 Sensors API corriendo en http://localhost:${PORT}`);
});
