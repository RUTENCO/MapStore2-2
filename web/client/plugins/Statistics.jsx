/*
 * Plugin Statistics - Dashboard de sensores
 * Renderiza la página /statistics con gráficas de recharts (estilo shadcn)
 */

import React, { useState, useEffect } from 'react';
import { createPlugin } from '../utils/PluginsUtils';
import SensorChart from './statistics/SensorChart';
import PeriodFilter from './statistics/PeriodFilter';
import SensorSelector from './statistics/SensorSelector';
import { fetchSensors, SENSORS as FALLBACK_SENSORS } from './statistics/mockData';
import '../themes/default/less/resources-catalog/_statistics-page.less';

function StatisticsContent() {
    const [period, setPeriod]   = useState('7d');
    const [sensors, setSensors] = useState(FALLBACK_SENSORS);
    const [active, setActive]   = useState(FALLBACK_SENSORS.map(s => s.id));

    useEffect(() => {
        fetchSensors().then(list => {
            if (list && list.length) {
                setSensors(list);
                setActive(list.map(s => s.id));
            }
        });
    }, []);

    return (
        <div className="ms-statistics-page">
            <div className="sc-dashboard">

                {/* Cabecera */}
                <div className="sc-dashboard__header">
                    <h1 className="sc-dashboard__title">Portafolio · Monitoreo de Sensores</h1>
                    <p className="sc-dashboard__subtitle">
                        Datos en tiempo real de la red de sensores ambientales
                    </p>
                </div>

                {/* Toolbar: filtros */}
                <div className="sc-dashboard__toolbar">
                    <PeriodFilter value={period} onChange={setPeriod} />
                    <SensorSelector sensors={sensors} active={active} onChange={setActive} />
                </div>

                {/* Grid de gráficas */}
                <div className="sc-dashboard__grid">
                    {active.map(sensorId => (
                        <SensorChart
                            key={sensorId}
                            sensorId={sensorId}
                            period={period}
                        />
                    ))}
                </div>

            </div>
        </div>
    );
}

export default createPlugin('Statistics', {
    component: StatisticsContent
});
