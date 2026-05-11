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

const rewritePrintUrl = (value) => {
    if (typeof value !== 'string') {
        return value;
    }
    return value
        .replace(/^https?:\/\/localhost:8081\//, 'http://geoserver:8080/')
        .replace(/^https?:\/\/localhost\/geoserver\//, 'http://geoserver:8080/geoserver/');
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
