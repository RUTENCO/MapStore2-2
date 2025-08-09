/*
 * Copyright 2024, GeoSolutions Sas.
 * All rights reserved.
 *
 * This source code is licensed under the BSD-style license found in the
 * LICENSE file in the root directory of this source tree.
 */

import React from 'react';
import PropTypes from 'prop-types';
import { Glyphicon } from 'react-bootstrap';

import { createPlugin } from "../../utils/PluginsUtils";
import Button from '../../components/layout/Button';
import Spinner from '../../components/layout/Spinner';
import Message from '../../components/I18N/Message';

// Importa los estilos del footer (ajusta la ruta si hace falta)
import '../../themes/default/less/resources-catalog/_footer.less';
import coColombia from '../../product/assets/img/co_colombia.png';
import logoGovCo from '../../product/assets/img/logo_gov_co.svg';

/**
 * Item de menú (compatibilidad en caso de volver a usar menuItems)
 */
function FooterMenuItem({
    className,
    loading,
    glyph,
    labelId,
    onClick,
    label
}) {
    return (
        <li>
            <Button
                onClick={onClick}
                className={className}
            >
                {loading ? <Spinner /> : <Glyphicon glyph={glyph} />}
                {' '}
                {labelId ? <Message msgId={labelId} /> : label}
            </Button>
        </li>
    );
}

FooterMenuItem.propTypes = {
    className: PropTypes.string,
    loading: PropTypes.bool,
    glyph: PropTypes.string,
    labelId: PropTypes.string,
    onClick: PropTypes.func,
    label: PropTypes.oneOfType([PropTypes.string, PropTypes.node])
};

FooterMenuItem.defaultProps = {
    onClick: () => {}
};

/**
 * Footer principal en flujo normal (no fixed).
 * Se renderiza al final del contenido, por lo que no necesita spacer.
 */
function Footer() {
    return (
        <footer id="ms-footer" className="ms-footer-custom" role="contentinfo">
            <div className="ms-footer-custom__container">

                {/* Bloque de marcas / logos */}
                <div className="ms-footer-custom__brands" aria-hidden="false">
                    <a
                        className="ms-footer-custom__brand-link"
                        href="https://colombia.co/"
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label="Colombia"
                    >
                        <img
                            className="ms-footer-custom__brand-img ms-footer-custom__brand-img--co"
                            src={coColombia}
                            alt="Colombia"
                        />
                    </a>

                    <div className="ms-footer-custom__separator" aria-hidden="true" />

                    <a
                        className="ms-footer-custom__brand-link"
                        href="https://www.gov.co/"
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label="Gov.co"
                    >
                        <img
                            className="ms-footer-custom__brand-img ms-footer-custom__brand-img--gov"
                            src={logoGovCo}
                            alt="Gov.co"
                        />
                    </a>
                </div>

                {/* Contenedor para acciones / links (derecha) */}
                <div className="ms-footer-custom__actions" aria-hidden="true">
                    {/* Aquí puedes añadir enlaces o botones si los necesitas */}
                </div>
            </div>
        </footer>
    );
}

Footer.propTypes = {
    // no recibimos height ni withResizeDetector en esta versión
};

export default createPlugin('Footer', {
    component: Footer
});
