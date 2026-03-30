/**
 * PeriodFilter.jsx
 * Botones para filtrar las gráficas por período de tiempo - estilo shadcn
 */

import React from 'react';
import PropTypes from 'prop-types';

export const PERIODS = [
    { value: '24h', label: 'Últimas 24h' },
    { value: '7d',  label: 'Últimos 7 días' },
    { value: '30d', label: 'Últimos 30 días' },
    { value: '90d', label: 'Últimos 90 días' }
];

function PeriodFilter({ value, onChange }) {
    return (
        <div className="sc-period-filter">
            <span className="sc-period-filter__label">Período:</span>
            <div className="sc-period-filter__buttons">
                {PERIODS.map(p => (
                    <button
                        key={p.value}
                        className={`sc-period-filter__btn${value === p.value ? ' sc-period-filter__btn--active' : ''}`}
                        onClick={() => onChange(p.value)}
                        type="button"
                    >
                        {p.label}
                    </button>
                ))}
            </div>
        </div>
    );
}

PeriodFilter.propTypes = {
    value: PropTypes.string.isRequired,
    onChange: PropTypes.func.isRequired
};

export default PeriodFilter;
