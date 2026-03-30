/**
 * mockData.js
 * Capa de datos para sensores.
 * → En desarrollo: llama a http://localhost:3001/api (proxy webpack → /api)
 * → En producción: llama a /api (nginx proxea a sensors-api:3001)
 *
 * El backend consulta Firebase Realtime Database.
 * Los datos quemados se mantienen como fallback si la API no está disponible.
 */

import { subDays, subHours, format } from 'date-fns';

// ── Base URL automática ───────────────────────────────────────────────
// En dev webpack proxea /api → localhost:3001
// En prod nginx proxea /api → sensors-api:3001
const API_BASE = '/api';
const LOCAL_API_PORT = '3001';
const DEFAULT_ZONE = 'Z1';
const DEFAULT_STATION = 'E1';

function isLocalHost() {
    if (typeof window === 'undefined') return false;
    return window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
}

function getApiBaseCandidates() {
    const candidates = [API_BASE];
    if (isLocalHost()) {
        candidates.push(`${window.location.protocol}//${window.location.hostname}:${LOCAL_API_PORT}/api`);
    }
    return [...new Set(candidates)];
}

async function fetchJSONWithApiFallback(path) {
    let lastError;
    const bases = getApiBaseCandidates();

    for (const base of bases) {
        try {
            const res = await fetch(`${base}${path}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            return await res.json();
        } catch (error) {
            lastError = error;
        }
    }

    throw lastError || new Error('No se pudo consultar la API de sensores');
}

function buildQuery(params = {}) {
    const cleaned = Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== '');
    if (!cleaned.length) return '';
    const search = new URLSearchParams(cleaned.map(([k, v]) => [k, String(v)]));
    return `?${search.toString()}`;
}

export const ZONES = [
    { id: 'Z1', name: 'Zona 1' },
    { id: 'Z2', name: 'Zona 2' },
    { id: 'Z3', name: 'Zona 3' },
    { id: 'Z4', name: 'Zona 4' }
];

export const STATIONS = [
    { id: 'E1', name: 'Estación 01' },
    { id: 'E2', name: 'Estación 02' },
    { id: 'E3', name: 'Estación 03' }
];

// ── Sensores (fallback local, se sobreescriben con datos reales) ──────
export const SENSORS = [
    { id: 'T1', name: 'Temperatura Suelo 1', unit: '°C', color: '#ef4444' },
    { id: 'H1', name: 'Humedad Suelo 1', unit: '%', color: '#3b82f6' },
    { id: 'T2', name: 'Temperatura Suelo 2', unit: '°C', color: '#f97316' },
    { id: 'H2', name: 'Humedad Suelo 2', unit: '%', color: '#6366f1' },
    { id: 'T3', name: 'Temperatura Suelo 3', unit: '°C', color: '#dc2626' },
    { id: 'H3', name: 'Humedad Suelo 3', unit: '%', color: '#2563eb' },
    { id: 'T4', name: 'Temperatura Aire', unit: '°C', color: '#f59e0b' },
    { id: 'H4', name: 'Humedad Aire', unit: '%', color: '#14b8a6' },
    { id: 'W1', name: 'Velocidad Viento', unit: 'm/s', color: '#8b5cf6' },
    { id: 'R1', name: 'Lluvia', unit: 'mm', color: '#0ea5e9' }
];

// ── Datos quemados de respaldo ────────────────────────────────────────
function generateReadings(sensorId, days = 30) {
    const now = new Date();
    const readings = [];
    const baseValues = { T1: 22, H1: 60, T2: 23, H2: 58, T3: 22, H3: 62, T4: 26, H4: 68, W1: 4.5, R1: 0.8 };
    const amplitude  = { T1: 5, H1: 12, T2: 5, H2: 12, T3: 5, H3: 12, T4: 7, H4: 14, W1: 3, R1: 2 };
    const base = baseValues[sensorId] ?? 50;
    const amp  = amplitude[sensorId]  ?? 10;
    const totalPoints = days * 4;
    for (let i = totalPoints; i >= 0; i--) {
        const date = subHours(now, i * 6);
        const noise = (Math.random() - 0.5) * amp;
        const trend = Math.sin((i / totalPoints) * Math.PI * 4) * amp * 0.5;
        readings.push({
            timestamp: date.toISOString(),
            label: format(date, 'dd/MM HH:mm'),
            value: parseFloat((base + trend + noise).toFixed(2))
        });
    }
    return readings;
}

export const FALLBACK_DATA = SENSORS.reduce((acc, s) => {
    acc[s.id] = generateReadings(s.id, 30);
    return acc;
}, {});

// ── API: obtener zonas ───────────────────────────────────────────────
export async function fetchZones() {
    try {
        return await fetchJSONWithApiFallback('/zones');
    } catch {
        return ZONES;
    }
}

// ── API: obtener estaciones por zona ─────────────────────────────────
export async function fetchStations(zone = DEFAULT_ZONE) {
    try {
        return await fetchJSONWithApiFallback(`/zones/${zone}/stations`);
    } catch {
        return STATIONS;
    }
}

// ── API: obtener lista de sensores ────────────────────────────────────
export async function fetchSensors(options = {}) {
    const zone = options.zone || DEFAULT_ZONE;
    const station = options.station || DEFAULT_STATION;
    try {
        const query = buildQuery({ zone, station });
        return await fetchJSONWithApiFallback(`/sensors${query}`);
    } catch {
        return SENSORS;
    }
}

// ── API: obtener lecturas de un sensor filtradas por período ──────────
export async function fetchReadings(sensorId, period = '7d', options = {}) {
    const zone = options.zone || DEFAULT_ZONE;
    const station = options.station || DEFAULT_STATION;
    try {
        const query = buildQuery({ period, zone, station });
        const rows = await fetchJSONWithApiFallback(`/sensors/${sensorId}/readings${query}`);
        // Normalizar: asegurar tipo numérico para Recharts
        return rows.map(r => ({
            ...r,
            value: parseFloat(r.value)
        }));
    } catch {
        // Fallback a datos quemados si la API no responde
        const all = FALLBACK_DATA[sensorId] ?? [];
        const now = new Date();
        const cutoff = {
            '24h': subHours(now, 24),
            '7d': subDays(now, 7),
            '30d': subDays(now, 30),
            '90d': subDays(now, 90)
        }[period] ?? subDays(now, 7);
        return all.filter(r => new Date(r.timestamp) >= cutoff);
    }
}

// ── API: estadísticas de un sensor ───────────────────────────────────
export async function fetchStats(sensorId, period = '7d', options = {}) {
    const zone = options.zone || DEFAULT_ZONE;
    const station = options.station || DEFAULT_STATION;
    try {
        const query = buildQuery({ period, zone, station });
        const s = await fetchJSONWithApiFallback(`/sensors/${sensorId}/stats${query}`);
        return {
            min: parseFloat(s.min).toFixed(2),
            avg: parseFloat(s.avg).toFixed(2),
            max: parseFloat(s.max).toFixed(2)
        };
    } catch {
        return null;
    }
}
