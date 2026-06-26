/*
 * Copyright 2017, GeoSolutions Sas.
 * All rights reserved.
 *
 * This source code is licensed under the BSD-style license found in the
 * LICENSE file in the root directory of this source tree.
 */

import main from './main';
import appConfig from './appConfig';
import pluginsDef from './plugins';
import { checkForMissingPlugins } from '../utils/DebugUtils';
import { addTransformer } from '../utils/PrintUtils';

checkForMissingPlugins(pluginsDef.plugins);

/**
 * Reescribe URLs de GeoServer al nombre interno del contenedor Docker
 * para que MapFish Print las alcance desde dentro de la red Docker.
 * Funciona para cualquier dominio de producción sin hardcodear el host.
 */
const rewritePrintUrl = (value) => {
    if (typeof value !== 'string') {
        return value;
    }
    // Dev: webpack dev server (8081) y nginx local
    let result = value
        .replace(/^https?:\/\/localhost:8081\//, 'http://geoserver:8080/')
        .replace(/^https?:\/\/localhost(?::\d+)?\/geoserver\//, 'http://geoserver:8080/geoserver/');
    // Producción: reescribir usando el hostname actual (sin hardcodear el dominio)
    if (typeof window !== 'undefined' && window.location?.hostname) {
        const host = window.location.hostname;
        if (host !== 'localhost' && host !== '127.0.0.1') {
            const escaped = host.replace(/\./g, '[.]');
            result = result.replace(
                new RegExp('^https?://(?:www[.])?' + escaped + '(?::[0-9]+)?/geoserver/'),
                'http://geoserver:8080/geoserver/'
            );
        }
    }
    return result;
};

addTransformer('rewritePrintUrls', (state, spec) => Promise.resolve({
    ...spec,
    layers: (spec.layers || []).map((layer) => ({
        ...layer,
        baseURL: rewritePrintUrl(layer.baseURL)
    })),
    legends: (spec.legends || []).map((legend) => ({
        ...legend,
        classes: (legend.classes || []).map((klass) => ({
            ...klass,
            icons: (klass.icons || []).map(rewritePrintUrl)
        }))
    }))
}));

main(appConfig, pluginsDef);
