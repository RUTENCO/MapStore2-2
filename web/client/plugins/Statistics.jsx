/*
 * Plugin Statistics - Dashboard de sensores
 * Renderiza la página /statistics con gráficas de recharts (estilo shadcn)
 */

import React, { useState, useEffect } from 'react';
import { createPlugin } from '../utils/PluginsUtils';
import SensorChart from './statistics/SensorChart';
import PeriodFilter from './statistics/PeriodFilter';
import LocationFilter from './statistics/LocationFilter';
import SensorSelector from './statistics/SensorSelector';
import {
    fetchZones,
    fetchStations,
    fetchSensors
} from './statistics/mockData';
import '../themes/default/less/resources-catalog/_statistics-page.less';

function StatisticsContent() {
    const [period, setPeriod]   = useState('30d');
    const [zone, setZone] = useState('');
    const [station, setStation] = useState('');
    const [zones, setZones] = useState([]);
    const [stations, setStations] = useState([]);
    const [sensors, setSensors] = useState([]);
    const [active, setActive]   = useState([]);

    useEffect(() => {
        fetchZones().then(list => {
            if (list && list.length) {
                setZones(list);
                if (!zone || !list.some(z => z.id === zone)) {
                    setZone(list[0].id);
                }
            } else {
                setZones([]);
                setZone('');
            }
        });
    }, []);

    useEffect(() => {
        if (!zone) {
            setStations([]);
            setStation('');
            return;
        }

        fetchStations(zone).then(list => {
            if (list && list.length) {
                setStations(list);
                if (!station || !list.some(s => s.id === station)) {
                    setStation(list[0].id);
                }
            } else {
                setStations([]);
                setStation('');
            }
        });
    }, [zone]);

    useEffect(() => {
        if (!zone || !station) return;

        fetchSensors({ zone, station }).then(list => {
            const finalList = list || [];
            setSensors(finalList);

            setActive(prev => {
                const validIds = new Set(finalList.map(s => s.id));
                const kept = prev.filter(id => validIds.has(id));
                return kept.length ? kept : finalList.map(s => s.id);
            });
        });
    }, [zone, station]);

    return (
        <div className="ms-statistics-page">
            <div className="sc-dashboard">

                {/* Cabecera */}
                <div className="sc-dashboard__header">
                    <h1 className="sc-dashboard__title">Monitoreo de Sensores</h1>
                    <p className="sc-dashboard__subtitle">
                        Datos en tiempo real de la red de sensores ambientales
                    </p>
                </div>

                {/* Toolbar: filtros */}
                <div className="sc-dashboard__toolbar">
                    <PeriodFilter value={period} onChange={setPeriod} />
                    <LocationFilter
                        zones={zones}
                        stations={stations}
                        zone={zone}
                        station={station}
                        onZoneChange={setZone}
                        onStationChange={setStation}
                    />
                    <SensorSelector sensors={sensors} active={active} onChange={setActive} />
                </div>

                {/* Grid de gráficas */}
                {sensors.length === 0 ? (
                    <div className="sc-dashboard__empty">
                        <h2 className="sc-dashboard__empty-title">No hay datos disponibles</h2>
                        <p className="sc-dashboard__empty-text">
                            La API no devolvió estaciones, sensores o lecturas para la selección actual.
                        </p>
                    </div>
                ) : (
                    <div className="sc-dashboard__grid">
                        {sensors
                            .filter(sensor => active.includes(sensor.id))
                            .map(sensor => (
                                <SensorChart
                                    key={sensor.id}
                                    sensor={sensor}
                                    period={period}
                                    zone={zone}
                                    station={station}
                                />
                            ))}
                    </div>
                )}

            </div>
        </div>
    );
}

export default createPlugin('Statistics', {
    component: StatisticsContent
});
