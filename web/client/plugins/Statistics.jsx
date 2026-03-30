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
    fetchSensors,
    SENSORS as FALLBACK_SENSORS,
    ZONES as FALLBACK_ZONES,
    STATIONS as FALLBACK_STATIONS
} from './statistics/mockData';
import '../themes/default/less/resources-catalog/_statistics-page.less';

function StatisticsContent() {
    const [period, setPeriod]   = useState('30d');
    const [zone, setZone] = useState('Z1');
    const [station, setStation] = useState('E1');
    const [zones, setZones] = useState(FALLBACK_ZONES);
    const [stations, setStations] = useState(FALLBACK_STATIONS);
    const [sensors, setSensors] = useState(FALLBACK_SENSORS);
    const [active, setActive]   = useState(FALLBACK_SENSORS.map(s => s.id));

    useEffect(() => {
        fetchZones().then(list => {
            if (list && list.length) {
                setZones(list);
                const validCurrentZone = list.some(z => z.id === zone);
                if (!validCurrentZone) {
                    setZone(list[0].id);
                }
            }
        });
    }, []);

    useEffect(() => {
        fetchStations(zone).then(list => {
            if (list && list.length) {
                setStations(list);
                const validCurrentStation = list.some(s => s.id === station);
                if (!validCurrentStation) {
                    setStation(list[0].id);
                }
            }
        });
    }, [zone]);

    useEffect(() => {
        if (!zone || !station) return;

        fetchSensors({ zone, station }).then(list => {
            const finalList = list && list.length ? list : FALLBACK_SENSORS;
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

            </div>
        </div>
    );
}

export default createPlugin('Statistics', {
    component: StatisticsContent
});
