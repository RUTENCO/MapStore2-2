/**
 * mockData.js
 * Capa de datos para sensores.
 * → En desarrollo: llama a http://localhost:3001/api  (proxy webpack → /api)
 * → En producción: llama a /api  (nginx proxea a sensors-api:3001)
 *
 * Los datos quemados se mantienen como fallback si la API no está disponible.
 */

import { subDays, subHours, format } from 'date-fns';

// ── Base URL automática ───────────────────────────────────────────────
// En dev webpack proxea /api → localhost:3001
// En prod nginx proxea /api → sensors-api:3001
const API_BASE = '/api';

// ── Sensores (fallback local, se sobreescriben con datos reales) ──────
export const SENSORS = [
    { id: 'S01', name: 'Temperatura Ambiente', unit: '°C',  color: '#ef4444' },
    { id: 'S02', name: 'Humedad Relativa',     unit: '%',   color: '#3b82f6' },
    { id: 'S03', name: 'Presión Atmosférica',  unit: 'hPa', color: '#10b981' },
    { id: 'S04', name: 'Velocidad del Viento', unit: 'm/s', color: '#f59e0b' }
];

// ── Datos quemados de respaldo ────────────────────────────────────────
function generateReadings(sensorId, days = 30) {
    const now = new Date();
    const readings = [];
    const baseValues = { S01: 22, S02: 65, S03: 1013, S04: 4 };
    const amplitude  = { S01: 6,  S02: 15, S03: 8,    S04: 3 };
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

// ── API: obtener lista de sensores ────────────────────────────────────
export async function fetchSensors() {
    try {
        const res = await fetch(`${API_BASE}/sensors`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
    } catch {
        return SENSORS;
    }
}

// ── API: obtener lecturas de un sensor filtradas por período ──────────
export async function fetchReadings(sensorId, period = '7d') {
    try {
        const res = await fetch(`${API_BASE}/sensors/${sensorId}/readings?period=${period}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const rows = await res.json();
        // Normalizar: la API devuelve value como string desde pg
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
            '30d': subDays(now, 30)
        }[period] ?? subDays(now, 7);
        return all.filter(r => new Date(r.timestamp) >= cutoff);
    }
}

// ── API: estadísticas de un sensor ───────────────────────────────────
export async function fetchStats(sensorId, period = '7d') {
    try {
        const res = await fetch(`${API_BASE}/sensors/${sensorId}/stats?period=${period}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const s = await res.json();
        return {
            min: parseFloat(s.min).toFixed(2),
            avg: parseFloat(s.avg).toFixed(2),
            max: parseFloat(s.max).toFixed(2)
        };
    } catch {
        return null;
    }
}
