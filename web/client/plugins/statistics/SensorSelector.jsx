/**
 * SensorSelector.jsx
 * Chips para seleccionar/deseleccionar sensores activos
 */

import React from 'react';
import PropTypes from 'prop-types';
import { SENSORS as DEFAULT_SENSORS } from './mockData';

function SensorSelector({ active, onChange, sensors }) {
    const list = (sensors && sensors.length) ? sensors : DEFAULT_SENSORS;

    function toggle(id) {
        if (active.includes(id)) {
            // No dejar deseleccionar el último
            if (active.length === 1) return;
            onChange(active.filter(s => s !== id));
        } else {
            onChange([...active, id]);
        }
    }

    return (
        <div className="sc-sensor-selector">
            <span className="sc-sensor-selector__label">Sensores:</span>
            <div className="sc-sensor-selector__chips">
                {list.map(s => (
                    <button
                        key={s.id}
                        type="button"
                        className={`sc-chip${active.includes(s.id) ? ' sc-chip--active' : ''}`}
                        style={active.includes(s.id) ? {
                            borderColor: s.color,
                            color: s.color,
                            background: s.color + '18'
                        } : {}}
                        onClick={() => toggle(s.id)}
                    >
                        <span
                            className="sc-chip__dot"
                            style={{ background: active.includes(s.id) ? s.color : '#d1d5db' }}
                        />
                        {s.name}
                    </button>
                ))}
            </div>
        </div>
    );
}

SensorSelector.propTypes = {
    active: PropTypes.arrayOf(PropTypes.string).isRequired,
    onChange: PropTypes.func.isRequired,
    sensors: PropTypes.array
};

export default SensorSelector;
