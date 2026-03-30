/**
 * LocationFilter.jsx
 * Selectores para zona y estación
 */

import React from 'react';
import PropTypes from 'prop-types';

function LocationFilter({ zones, stations, zone, station, onZoneChange, onStationChange }) {
    return (
        <div className="sc-location-filter">
            <div className="sc-location-filter__group">
                <label className="sc-location-filter__label" htmlFor="sc-zone">Zona:</label>
                <select
                    id="sc-zone"
                    className="sc-location-filter__select"
                    value={zone}
                    onChange={e => onZoneChange(e.target.value)}>
                    {zones.map(z => (
                        <option key={z.id} value={z.id}>{z.name || z.id}</option>
                    ))}
                </select>
            </div>

            <div className="sc-location-filter__group">
                <label className="sc-location-filter__label" htmlFor="sc-station">Estación:</label>
                <select
                    id="sc-station"
                    className="sc-location-filter__select"
                    value={station}
                    onChange={e => onStationChange(e.target.value)}>
                    {stations.map(s => (
                        <option key={s.id} value={s.id}>{s.name || s.id}</option>
                    ))}
                </select>
            </div>
        </div>
    );
}

LocationFilter.propTypes = {
    zones: PropTypes.arrayOf(PropTypes.shape({
        id: PropTypes.string,
        name: PropTypes.string
    })).isRequired,
    stations: PropTypes.arrayOf(PropTypes.shape({
        id: PropTypes.string,
        name: PropTypes.string
    })).isRequired,
    zone: PropTypes.string.isRequired,
    station: PropTypes.string.isRequired,
    onZoneChange: PropTypes.func.isRequired,
    onStationChange: PropTypes.func.isRequired
};

export default LocationFilter;
