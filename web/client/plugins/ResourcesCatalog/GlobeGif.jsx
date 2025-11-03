/*
 * Copyright 2025, Tu Organización.
 * All rights reserved.
 *
 * Este código fuente está licenciado bajo la licencia BSD que se encuentra en el archivo LICENSE en el directorio raíz de este proyecto.
 */

import React, { useState, useEffect } from 'react';
import { createPlugin } from '../../utils/PluginsUtils';
import { withResizeDetector } from 'react-resize-detector';
import Message from '../../components/I18N/Message';

// Importamos la función para obtener datos de Strapi
// import { getHomeInfo } from '../../libs/strapi/get-home-info.js';

// Importamos el gif
import amanecerGif from '../../product/assets/img/amanecer.gif';
import wrfGif from '../../product/assets/img/wrf.gif';

function GlobeGif() {

    // const [wrfGifUrl, setWrfGifUrl] = useState(null);
    const [dateTime, setDateTime] = useState(new Date());

    /* useEffect(() => {
        getHomeInfo().then(({ image }) => {
            setWrfGifUrl(image);
        });
    }, []); */


    useEffect(() => {
        const interval = setInterval(() => {
            setDateTime(new Date());
        }, 1000);
        return () => clearInterval(interval);
    }, []);

    const fecha = dateTime.toLocaleDateString('es-CO', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
    const hora = dateTime.toLocaleTimeString('es-CO');

    return (
        <div className="ms-globe-gif-container">
            <h3 className="ms-globe-title">
                <Message msgId="globe.title" defaultMessage="Amanecer" />
            </h3>
            <p className="ms-globe-datetime">
                {fecha} — {hora}
            </p>
            <div className="ms-globe-wrapper ms-globe-gif-row">
                <a href="https://zoom.earth/" target="_blank" rel="noopener noreferrer">
                    <img
                        src={amanecerGif}
                        alt="Globo Tierra Amanecer"
                        className="ms-globe-gif"
                        style={{ cursor: 'pointer' }}
                    />
                </a>
                <a href="#" target="_self" rel="noopener noreferrer">
                    <img
                        src={wrfGif} // wrfGifUrl
                        alt="WRF Model GIF"
                        className="ms-wrf-gif"
                        style={{ cursor: 'pointer' }}
                    />
                </a>
                {/* {wrfGif && ( // wrfGifUrl
                    <a href="#" target="_self" rel="noopener noreferrer">
                        <img
                            src={wrfGif} // wrfGifUrl
                            alt="WRF Model GIF"
                            className="ms-wrf-gif"
                            style={{ cursor: 'pointer' }}
                        />
                    </a>
                )} */}
            </div>
        </div>
    );
}

export default createPlugin('GlobeGif', {
    component: withResizeDetector(GlobeGif)
});
