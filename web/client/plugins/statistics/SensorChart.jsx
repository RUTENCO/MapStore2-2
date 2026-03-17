/**
 * SensorChart.jsx
 * Gráfica de línea para un sensor individual - estilo shadcn/ui
 * Consume datos desde la API REST (Neon PostgreSQL) con fallback a datos locales
 */

import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import {
    ResponsiveContainer,
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip
} from 'recharts';
import { fetchReadings, SENSORS } from './mockData';

// ── Tooltip personalizado (look shadcn) ───────────────────────────────
function CustomTooltip({ active, payload, label, unit }) {
    if (!active || !payload || !payload.length) return null;
    return (
        <div className="sc-tooltip">
            <p className="sc-tooltip__label">{label}</p>
            <p className="sc-tooltip__value">
                {payload[0].value} <span className="sc-tooltip__unit">{unit}</span>
            </p>
        </div>
    );
}

CustomTooltip.propTypes = {
    active: PropTypes.bool,
    payload: PropTypes.array,
    label: PropTypes.string,
    unit: PropTypes.string
};

// ── Estadísticas rápidas (calculadas localmente desde los datos) ──────
function Stats({ data }) {
    if (!data.length) return null;
    const values = data.map(d => d.value);
    const min = Math.min(...values).toFixed(2);
    const max = Math.max(...values).toFixed(2);
    const avg = (values.reduce((a, b) => a + b, 0) / values.length).toFixed(2);
    return (
        <div className="sc-stats">
            <span className="sc-stats__item"><em>Mín</em>{min}</span>
            <span className="sc-stats__item"><em>Prom</em>{avg}</span>
            <span className="sc-stats__item"><em>Máx</em>{max}</span>
        </div>
    );
}

Stats.propTypes = { data: PropTypes.array };

// ── Skeleton de carga ─────────────────────────────────────────────────
function ChartSkeleton() {
    return (
        <div className="sc-card__skeleton">
            <div className="sc-card__skeleton-bar" style={{ width: '60%' }} />
            <div className="sc-card__skeleton-bar" style={{ width: '40%' }} />
            <div className="sc-card__skeleton-chart" />
        </div>
    );
}

// ── Componente principal ──────────────────────────────────────────────
function SensorChart({ sensorId, period }) {
    const sensor = SENSORS.find(s => s.id === sensorId);
    const [data, setData]       = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        setLoading(true);
        fetchReadings(sensorId, period)
            .then(rows => setData(rows))
            .finally(() => setLoading(false));
    }, [sensorId, period]);

    const tickInterval = Math.max(1, Math.floor(data.length / 12));

    if (!sensor) return null;

    return (
        <div className="sc-card">
            {/* Cabecera */}
            <div className="sc-card__header">
                <span className="sc-card__indicator" style={{ background: sensor.color }} />
                <div>
                    <h3 className="sc-card__title">{sensor.name}</h3>
                    <p className="sc-card__subtitle">Sensor {sensor.id} · {sensor.unit}</p>
                </div>
            </div>

            {loading ? <ChartSkeleton /> : (
                <>
                    <Stats data={data} />
                    <div className="sc-card__chart">
                        {data.length === 0 ? (
                            <p className="sc-card__empty">Sin datos para este período</p>
                        ) : (
                            <ResponsiveContainer width="100%" height={200}>
                                <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis
                                        dataKey="label"
                                        tick={{ fontSize: 10, fill: '#888' }}
                                        interval={tickInterval}
                                        tickLine={false}
                                        axisLine={{ stroke: '#e5e7eb' }}
                                    />
                                    <YAxis
                                        tick={{ fontSize: 10, fill: '#888' }}
                                        tickLine={false}
                                        axisLine={false}
                                        width={42}
                                    />
                                    <Tooltip
                                        content={<CustomTooltip unit={sensor.unit} />}
                                        cursor={{ stroke: sensor.color, strokeWidth: 1, strokeDasharray: '4 2' }}
                                    />
                                    <Line
                                        type="monotone"
                                        dataKey="value"
                                        stroke={sensor.color}
                                        strokeWidth={2}
                                        dot={false}
                                        activeDot={{ r: 4, fill: sensor.color }}
                                    />
                                </LineChart>
                            </ResponsiveContainer>
                        )}
                    </div>
                </>
            )}
        </div>
    );
}

SensorChart.propTypes = {
    sensorId: PropTypes.string.isRequired,
    period: PropTypes.string.isRequired
};

export default SensorChart;
